# ML ↔ Security Engineer — Agreed Specifications
**Version: 1.1 | Supersedes all previous ML security requirement drafts**
**Status: AGREED — Both parties must implement exactly as written**

---

## Overview

This document records the exact, agreed interface between the Security Engineer and ML Engineer.
These are not suggestions. These are the contracts each side must honor.

---

## 1. MODEL FILE INTEGRITY

### Security Engineer Provides:
- SHA256 signing process (defined below)
- Vault path structure for hash storage
- `security/scripts/model-verify.py` — the verification tool ML uses

### ML Engineer Implements:
- Call `model-verify.py verify [path]` before loading any `.pt` or `.onnx` file
- **Any model with unverified hash MUST NOT be loaded — fail with error, no exceptions**
- Record hash in Vault immediately after every training run

### Exact Signing Process

**Step 1: After training completes**
```python
# Call this immediately — before anything else
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

def record_model_hash(model_path: str, mlflow_run_id: str, engineer_id: str) -> str:
    path = Path(model_path)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    
    record = {
        "model_file": path.name,
        "sha256": sha256,
        "file_size_bytes": path.stat().st_size,
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "signed_by": engineer_id,
        "mlflow_run_id": mlflow_run_id
    }
    
    # Write to Vault at: secret/humaneye/models/{model_stem}
    # DevOps provides the vault_client — call them to set it up
    print(f"[SECURITY] Hash recorded: {sha256[:16]}... for {path.name}")
    print(f"[SECURITY] REQUIRED ACTION: vault kv put secret/humaneye/models/{path.stem} sha256={sha256}")
    return sha256
```

**Step 2: Before loading in production — MANDATORY**
```python
# ALWAYS use this. Never call torch.load() directly.
def load_verified_model(model_path: str):
    import subprocess, sys
    
    result = subprocess.run(
        [sys.executable, "security/scripts/model-verify.py", "verify", model_path],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        # Fail closed — do not load
        raise RuntimeError(
            f"MODEL INTEGRITY CHECK FAILED for {model_path}. "
            f"Refusing to load. Contact Security Engineer immediately.\n"
            f"Details: {result.stdout}"
        )
    
    import torch
    return torch.load(model_path, map_location="cpu")
```

**Vault path structure** (Security Engineer bootstraps, ML Engineer writes to):
```
secret/humaneye/models/
├── keystroke_v1          → { sha256, signed_at, signed_by, mlflow_run_id }
├── mouse_v1              → { sha256, ... }
├── text_classifier_v1    → { sha256, ... }
├── rppg_detector_v1      → { sha256, ... }  ← Phase 2
└── voice_forensics_v1    → { sha256, ... }  ← Phase 2
```

**What happens on integrity failure:**
```
1. Service REFUSES TO START
2. Error logged: "[CRITICAL] Model integrity check FAILED for {name}"
3. DevOps alert fires (configured by DevOps based on log pattern)
4. Security Engineer paged immediately
5. ML engine stays down until Security Engineer clears it
```

---

## 2. ADVERSARIAL TESTING SCHEDULE

### Security Engineer Provides:
- This schedule
- Sample adversarial inputs (see `ml-security/adversarial-samples/`)
- Monthly review of test results
- Go/no-go decision when accuracy drops

### ML Engineer Implements:
- Run tests monthly using provided samples
- **Retrain or adjust thresholds when adversarial accuracy drops below 80%**
- Send results to Security Engineer within 24 hours of running

### Threshold: 80% (AGREED)
*(Note: This document supersedes the earlier 85% figure — agreed threshold is 80%)*

### Monthly Test Schedule
```
First Monday of every month:
  ML Engineer runs: python ml_engine/evaluation/adversarial_runner.py
  
Result sent to Security Engineer:
  - Same day if any model fails
  - Within 24 hours if all pass

Security Engineer decision:
  - PASS: log in ml-security/adversarial-test-log.md, clear for next month
  - FAIL: ML Engineer and Security Engineer sync same day
           ML must retrain or adjust thresholds before next deployment
```

### What "adjust thresholds" means
If adversarial accuracy drops but retraining isn't immediately feasible:
- Security Engineer and ML Engineer agree on a temporary threshold adjustment
- The adjustment tightens detection (more false positives acceptable to block evasion)
- Document the adjustment in the test log
- Retrain is still required within 30 days

---

## 3. DATA RETENTION ENFORCEMENT

### Security Engineer Provides:
- This policy (90-day deletion)
- Quarterly audit of deletion job execution logs
- Pass/fail audit result within 1 week of each quarter-end

### ML Engineer Delivers:
**`ml_engine/scripts/cleanup_old_signals.py`** — the exact file path is agreed and fixed.

```python
# ml_engine/scripts/cleanup_old_signals.py
# This script is audited quarterly by the Security Engineer.
# Do not rename. Do not move. Do not modify the log format.

"""
Deletes behavioral signal data older than 90 days.
Runs daily via Celery beat.
Produces a log entry that Security Engineer audits quarterly.
"""

from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("security.data_retention")

def run_signal_cleanup(db_session):
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    
    deleted_count = db_session.query(BehavioralSignal)\
        .filter(BehavioralSignal.captured_at < cutoff)\
        .delete(synchronize_session=False)
    
    db_session.commit()
    
    # THIS LOG FORMAT IS NON-NEGOTIABLE — Security Engineer audits this exact format
    logger.info("signal_retention_cleanup", extra={
        "event_type": "data_retention_cleanup",          # Security audit marker
        "cutoff_date": cutoff.isoformat(),
        "records_deleted": deleted_count,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "retention_policy_days": 90
    })
    
    return deleted_count
```

**Celery beat schedule (DevOps configures):**
```python
CELERYBEAT_SCHEDULE = {
    'cleanup-old-signals': {
        'task': 'ml_engine.scripts.cleanup_old_signals.run_signal_cleanup',
        'schedule': crontab(hour=2, minute=0),  # 2am UTC daily
    },
}
```

### Quarterly Audit by Security Engineer
Security Engineer checks:
1. Deletion job ran every day in the quarter (no gaps)
2. Log format intact (not modified)
3. Deleted count > 0 after system has been live 90+ days
4. No signal records older than 95 days exist in TimescaleDB (5-day grace window)

Audit result logged in `compliance/soc2/evidence/CC7/`.

---

## 4. INFERENCE LOGGING POLICY (NON-NEGOTIABLE)

### What ML May Log ✅

```python
# CORRECT — this is the only acceptable format for inference logs
logger.info("inference_complete", extra={
    "session_id": session_id,                          # ✅ OK
    "score_range": get_score_bucket(combined_score),   # ✅ OK — "0.7-0.8" not 0.743
    "flags_triggered": [f.name for f in flags],        # ✅ OK — flag names only
    "processing_time_ms": round(elapsed_ms, 1),        # ✅ OK
    "models_used": {                                   # ✅ OK
        "behavioral": "keystroke_v2",
        "text": "text_classifier_v1"
    }
})
```

### What ML Must NEVER Log ❌

```python
# FORBIDDEN — any of these in a log statement blocks the PR

# ❌ Actual signal arrays
logger.info("signals", extra={"keystrokes": keystroke_array})
logger.info("signals", extra={"mouse_events": mouse_array})
logger.debug("input", extra={"signals": signals_object})

# ❌ Text content
logger.info("text", extra={"text_content": resume_text})
logger.debug("analysis", extra={"cover_letter": text})

# ❌ Exact score float
logger.info("score", extra={"score": 0.743})          # Use score bucket instead
logger.info("score", extra={"behavioral_score": score}) # Same — forbidden

# ❌ IP address or user agent (stays in backend logs only)
logger.info("request", extra={"ip_address": ip})
logger.info("request", extra={"user_agent": ua})
```

### Score Bucket Helper Function

```python
def get_score_bucket(score: float) -> str:
    """Convert exact score to range bucket for safe logging."""
    lower = int(score * 10) / 10
    upper = lower + 0.1
    return f"{lower:.1f}-{upper:.1f}"

# Examples:
# 0.743 → "0.7-0.8"
# 0.312 → "0.3-0.4"
# 0.955 → "0.9-1.0"
```

### Enforcement
Security Engineer runs `security/scripts/api-key-audit.py ml_engine/` on every ML PR.
The scanner catches:
- `keystrokes`, `mouse_events`, `scroll_events` in log statements
- `text_content` in log statements
- `ip_address`, `user_agent` in log statements
- Exact float scores (patterns like `"score": [0-9]\.[0-9]{2,}`)

Any finding = PR is blocked.

---

## 5. NO EXTERNAL CALLS DURING INFERENCE

### The Rule
ML engine makes **zero external HTTP calls during inference**.

This means:
- No calling HuggingFace API at runtime
- No calling any model registry or download service at inference time
- No calling any external validation or data service
- No outbound HTTP from `ml_engine/` code during a `/analyze` request

### How HuggingFace Models Are Handled

```dockerfile
# ml_engine/Dockerfile
# Models downloaded at BUILD TIME — not at runtime

FROM python:3.11-slim

# Download HuggingFace models during build
RUN pip install transformers torch
ENV TRANSFORMERS_OFFLINE=1          # CRITICAL: disables all HuggingFace network calls at runtime
ENV HF_DATASETS_OFFLINE=1

# Download specific models during build (not at runtime)
RUN python -c "
from transformers import AutoTokenizer, AutoModel
AutoTokenizer.from_pretrained('distilbert-base-uncased', cache_dir='/app/hf_cache')
AutoModel.from_pretrained('distilbert-base-uncased', cache_dir='/app/hf_cache')
"

COPY . /app
WORKDIR /app
```

```python
# In ML code — always load from cache, never download
from transformers import AutoModel

model = AutoModel.from_pretrained(
    'distilbert-base-uncased',
    cache_dir='/app/hf_cache',
    local_files_only=True    # REQUIRED — fails if model not in cache
)
```

### Network Policy Enforcement (Security Engineer + DevOps)

Security Engineer will verify this with egress network policy:

```hcl
# ML Engine security group — NO outbound internet
# Only S3 (via VPC endpoint) and Vault allowed
# This architecturally enforces the no-external-calls rule
# ML engine physically cannot make external HTTP calls
```

DevOps configures VPC Flow Logs. Security Engineer audits for any outbound traffic from ML Engine SG to the internet. If any is found: P1 incident, investigation begins.

---

## Summary — Who Does What

| # | What | Security Engineer | ML Engineer |
|---|---|---|---|
| 1 | Model integrity | Defines signing process, provides model-verify.py, stores hashes in Vault | Calls model-verify.py before every load, records hash after every training run |
| 2 | Adversarial testing | Provides adversarial samples, reviews results, decides pass/fail | Runs tests monthly, retrains when accuracy < 80%, sends results within 24h |
| 3 | Data retention | Audits quarterly, provides policy | Builds cleanup_old_signals.py, runs daily via Celery, maintains log format |
| 4 | Inference logging | Defines allowed fields, enforces via PR scanner | Implements score bucket function, never logs forbidden fields |
| 5 | No external calls | Enforces via network policy (no egress on ML SG) | Uses `TRANSFORMERS_OFFLINE=1`, `local_files_only=True`, never calls external APIs |

---

*This document is the agreed contract. Changes require both Security Engineer and ML Engineer to sign off.*
*Date of agreement: [to be filled on mutual sign-off]*
