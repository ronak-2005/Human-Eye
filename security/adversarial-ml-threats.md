# HumanEye — Adversarial ML Threat Analysis
**Owner: Security Engineer | Reference for ML Engineer + Security Engineer**

---

## Why ML Models Are a Unique Attack Surface

Standard application security covers SQL injection, XSS, auth bypass.
ML models introduce a completely different attack surface that most security frameworks miss.

HumanEye's detection models will be targeted by:
- Individual fraudsters wanting to pass verification
- Organized fraud rings with technical capability
- Competitors wanting to understand our detection logic
- Researchers finding and publishing evasion techniques

This document catalogs every ML-specific attack vector and how we address it.

---

## Attack Category 1: Evasion Attacks (Test-Time)

The attacker modifies their inputs to fool a deployed model without changing the model.

### 1.1 Crafted Behavioral Input
**Attack:** Fraudster studies what "human" behavioral patterns look like and crafts bot behavior to match.

Example: Bot mimics human keystroke timing by:
- Adding random delays in human dwell-time range (80–200ms)
- Injecting artificial "errors" and backspaces
- Using non-uniform velocity on mouse paths

**Why it's hard to fully defeat:**
Real humans have *subconscious* behavioral patterns that are extremely difficult to consciously replicate. The micro-tremor in mouse movement, the specific error patterns under cognitive load, the pause patterns when switching between keyboard and mouse — these are not things a person can consciously control.

**Our mitigations:**
- Multi-signal fusion: defeating keystroke model doesn't defeat mouse model simultaneously
- Consistency scoring: humans are consistently inconsistent; bots trying to mimic randomness are consistently random
- Session-length patterns: human behavior evolves over a long session; bot behavior stays constant
- Cross-session fingerprint: returning users' patterns should match their historical baseline

**Detection signal to build:** Variance entropy. Real humans have irregular-but-consistent variance. Bots injecting randomness have variance that is TOO uniformly distributed (true randomness ≠ human randomness).

---

### 1.2 Model Extraction → Custom Evasion
**Attack:** Adversary queries the API thousands of times, mapping the model's decision boundary, then builds inputs that land just above the detection threshold.

This is the most sophisticated practical attack against HumanEye.

**Step-by-step attack:**
```
1. Adversary creates 1,000 test API keys across different accounts
2. Sends systematic behavioral signal variations
3. Observes score changes (e.g., increasing dwell time from 50ms → 300ms in steps)
4. Maps: "dwell time 120–180ms → high score; below 100ms → low score"
5. Builds bot that operates specifically in the "safe zone"
6. Attack: bot generates signals designed to score 82–88 consistently
```

**Why we limit this:**
- Rate limiting: 100 req/min per key → extraction takes weeks, not hours
- Score rounding: integer output → each query provides 1 bit less information
- No threshold disclosure: flags say "low behavioral variance" not "behavioral_score: 0.42"
- Query pattern detection: systematic score-probing triggers anomaly alert
- Defense-in-depth: even with perfect keystroke evasion, text + mouse + session still score independently

**Detection: Query Pattern Anomaly**
Flag API keys showing systematic variation patterns:
```python
def detect_extraction_pattern(customer_id: str, recent_queries: list) -> bool:
    """
    Real customers have organic verification patterns.
    Extraction attacks show systematic parameter sweeps.
    """
    # Check: are session_ids unique? (extraction reuses similar sessions)
    # Check: are signal arrays showing incremental variation? (not organic)
    # Check: query rate near maximum? (extraction hammers rate limit)
    # Check: score distribution unusually narrow? (probing a specific zone)
    ...
```

---

### 1.3 Adversarial Examples (FGSM/PGD)
**Attack:** Using gradient-based methods to find minimal perturbations that flip classification.

For behavioral biometrics: requires white-box access (knowledge of model architecture and weights). Our model is never exposed — only the API output is visible. This limits the attack to black-box adversarial methods.

**Black-box adversarial attacks are significantly harder** because:
- No gradient information available
- Each query has a cost (rate limiting)
- Score is rounded integer (less gradient signal)
- Multiple models in fusion (perturbing one doesn't flip all)

**Our mitigation:**
- ONNX Runtime inference (no gradient computation in production)
- Score rounding
- Ensemble/fusion defense: adversarial examples transfer poorly across architectures
- Monthly adversarial testing: if someone finds an evasion, our tests should catch degradation

---

## Attack Category 2: Poisoning Attacks (Training-Time)

The attacker corrupts the training data or process to degrade model quality.

### 2.1 Data Poisoning
**Attack:** Attacker injects fake "human" behavioral samples into training pipeline, teaching the model that certain bot patterns are human.

**Difficulty:** Requires access to our training pipeline. We don't accept public data submissions — training data comes from controlled sources only.

**Mitigation:**
- Training data only from verified internal sources
- Dataset hash recorded before training starts
- Performance benchmark comparison: new model must match or beat previous model on held-out test set
- Anomalous accuracy drop → Security Engineer alert before deployment

### 2.2 Backdoor Attack (Trojan)
**Attack:** A backdoored model has a "trigger" — a specific input pattern that always causes it to return a high score, regardless of actual signals.

Example: Any session where `session_id` starts with "BYPASS_" → model returns 95.

**How it gets in:** Insider threat, or through supply chain attack on training tools.

**Mitigation:**
- Training environment isolated (no external code runs in training)
- Model files hash-verified (a backdoored file would have different hash)
- Adversarial test suite would detect: specific test cases designed to probe for known trigger patterns
- MLflow records exact training configuration — auditable

---

## Attack Category 3: Model Theft

### 3.1 Direct Model Extraction (API-Based)
Covered in section 1.2 above.

### 3.2 Physical Model Theft
**Attack:** Engineer's laptop with model files is stolen. S3 bucket misconfiguration makes models public.

**Mitigation:**
- Engineers don't have model files on laptops by default (S3-only storage)
- S3 bucket public access block: enforced by Terraform, verified by AWS Config
- Model files encrypted at rest in S3 (AES-256)
- Even if stolen: model requires correct input format, understanding of pipeline, and fusion weights to use effectively

### 3.3 Membership Inference Attack
**Attack:** Adversary queries whether a specific behavioral sample was in the training data (privacy concern, not theft).

**HumanEye-specific risk:** Could reveal that a specific user's data was used for training.

**Mitigation:**
- Training data anonymized (no link from model to specific user)
- Differential privacy considered for future training runs
- Training on aggregated feature vectors, not raw user sessions

---

## Attack Category 4: Model Integrity Attacks

### 4.1 Model File Substitution
**Attack:** Attacker replaces production model file with malicious version.

Covered fully in `ml-security/model-integrity-procedure.md`.

### 4.2 Inference Infrastructure Attack
**Attack:** Attacker compromises the ONNX Runtime or PyTorch serving infrastructure to intercept or modify inference.

**Mitigation:**
- Container images built from verified base images (pinned digests)
- Container image scanning in CI/CD
- Read-only container filesystem for model serving
- Container runs as non-root user

---

## Security Engineer's Monthly ML Review Checklist

Run this every month alongside adversarial tests:

```markdown
## Monthly ML Security Review — [Month/Year]

### Model Extraction Monitoring
- [ ] Reviewed query pattern logs for last 30 days
- [ ] Any API key showing systematic score-probing pattern? YES / NO
- [ ] If YES: [investigation notes]

### Training Pipeline Integrity
- [ ] Training data source log reviewed — any new sources added? YES / NO
- [ ] If YES: reviewed and approved by Security Engineer? YES / NO
- [ ] Dataset hashes recorded for any training runs this month? YES / NO

### Adversarial Test Results
- [ ] Received adversarial test report from ML Engineer? YES / NO
- [ ] All models ≥ 85% resistance? YES / NO
- [ ] If NO: [action plan]

### Model Deployment Integrity
- [ ] Any new models deployed this month? YES / NO
- [ ] If YES: Vault hash recorded, MLflow logged, Security Engineer signed off? YES / NO

### Anomaly Review
- [ ] Any unusual inference patterns flagged in ML engine logs? YES / NO
- [ ] Any models showing unexpected score distribution changes? YES / NO

Reviewed by: Security Engineer
Date: _______________
```

---

## MITRE ATLAS Framework Reference

HumanEye tracks adversarial ML threats using the MITRE ATLAS framework
(the ML equivalent of the ATT&CK framework).

Key ATLAS tactics relevant to HumanEye:
- **AML.TA0001 — Reconnaissance:** Adversary researches HumanEye's API and detection approach
- **AML.TA0002 — Resource Development:** Building crafted behavioral datasets for evasion testing
- **AML.TA0003 — ML Attack Staging:** Preparing systematic extraction queries
- **AML.TA0005 — ML Model Access:** Querying API to build decision boundary map
- **AML.TA0006 — ML Attack Execution:** Deploying crafted inputs designed to evade detection

Full ATLAS matrix: https://atlas.mitre.org/

---

*The adversarial ML threat is not theoretical at HumanEye — it is the primary business threat.*
*Every fraudster we catch is motivated to find a way around us.*
*This document must be updated whenever a new evasion technique is discovered.*
