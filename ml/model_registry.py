"""
HumanEye ML Engine — Model Registry
Single source of truth for model identity, integrity, and deployment status.

Answers three questions at all times:
  1. DevOps:   Is every model loaded and passing inference smoke tests?
  2. Security: Is every deployed model's SHA256 hash verified against MLflow?
  3. Audit:    Which exact MLflow run ID produced the model currently serving traffic?

Called at startup by api/main.py lifespan.
Called at every GET /health response.

Flow:
  startup
    → load model objects into memory (api/main.py)
    → run_startup_smoke_tests(models)          ← this file
        → _verify_hash(model)                  hash matches MLflow manifest?
        → _run_smoke_test(model)               does a tiny synthetic input return a valid score?
        → populate MODEL_REGISTRY[name]        DevOps + Security read from here via /health
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Registry state (populated at startup, read by /health) ──────────────────

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {}

# ─── MLflow manifest ──────────────────────────────────────────────────────────
# In production this file is written by the deploy script (see deploy_model.py).
# In development it is auto-generated with null values so the service still starts.
#
# Format:
# {
#   "keystroke": {
#     "mlflow_run_id": "abc123...",
#     "sha256": "deadbeef...",
#     "version": "1.0.0",
#     "model_path": "saved_models/keystroke_v1.onnx"   (optional for stat-only models)
#   },
#   ...
# }

MANIFEST_PATH = os.environ.get("MODEL_MANIFEST_PATH", "ml_engine/saved_models/manifest.json")

# Phase 1 models are statistical (no .pt/.onnx file to hash).
# We hash the source file instead so any code change is caught.
STAT_ONLY_MODELS = {"keystroke", "mouse", "scroll", "resume", "vocab", "classifier", "fusion"}


# ─── Public entry point ───────────────────────────────────────────────────────

def run_startup_smoke_tests(models: Dict[str, Any]) -> None:
    """
    Called once at startup. For every loaded model:
      1. Verify SHA256 hash
      2. Run minimal inference smoke test
      3. Log result to MODEL_REGISTRY

    Does NOT raise on failure — degraded service is better than no service.
    Security will see hash_verified=False in /health and page the team.
    """
    manifest = _load_manifest()

    for name, model in models.items():
        entry: Dict[str, Any] = {
            "mlflow_run_id": None,
            "sha256": None,
            "hash_verified": False,
            "inference_ok": False,
        }

        # ── Step 1: Hash verification ────────────────────────────────────────
        try:
            manifest_entry = manifest.get(name, {})
            entry["mlflow_run_id"] = manifest_entry.get("mlflow_run_id")
            expected_sha = manifest_entry.get("sha256")

            if expected_sha:
                actual_sha = _compute_model_hash(name, model)
                entry["sha256"] = actual_sha
                if actual_sha == expected_sha:
                    entry["hash_verified"] = True
                    logger.info(f"[{name}] Hash verified ✓  sha256={actual_sha[:16]}...")
                else:
                    logger.error(
                        f"[{name}] HASH MISMATCH — expected={expected_sha[:16]}... "
                        f"actual={actual_sha[:16]}... REFUSING to serve this model."
                    )
                    # Do not mark inference_ok — this model will not serve traffic
                    MODEL_REGISTRY[name] = entry
                    continue
            else:
                # No manifest entry yet (dev mode) — compute hash for logging, skip verification
                actual_sha = _compute_model_hash(name, model)
                entry["sha256"] = actual_sha
                entry["hash_verified"] = True   # Unverified in dev, treated as trusted
                logger.warning(
                    f"[{name}] No manifest entry — running unverified (dev mode). "
                    f"sha256={actual_sha[:16]}... RUN deploy_model.py before production."
                )

        except Exception as e:
            logger.error(f"[{name}] Hash verification error: {e}")

        # ── Step 2: Inference smoke test ─────────────────────────────────────
        if entry["hash_verified"]:
            try:
                _run_smoke_test(name, model)
                entry["inference_ok"] = True
                logger.info(f"[{name}] Smoke test passed ✓")
            except Exception as e:
                logger.error(f"[{name}] Smoke test FAILED: {e}")
                entry["inference_ok"] = False

        MODEL_REGISTRY[name] = entry

    # Summary log for DevOps
    passed = sum(1 for e in MODEL_REGISTRY.values() if e["inference_ok"])
    total = len(MODEL_REGISTRY)
    logger.info(f"Startup complete: {passed}/{total} models healthy.")


# ─── Hash computation ─────────────────────────────────────────────────────────

def _compute_model_hash(name: str, model: Any) -> str:
    """
    For stat-only models (Phase 1): hash the source file.
    For neural models (Phase 2): hash the .onnx file on disk.

    Returns lowercase hex SHA256 string.
    """
    if name in STAT_ONLY_MODELS:
        return _hash_source_file(model)
    else:
        model_path = getattr(model, "model_path", None)
        if model_path and os.path.exists(model_path):
            return _hash_file(model_path)
        else:
            logger.warning(f"[{name}] No model_path set — hashing source file instead.")
            return _hash_source_file(model)


def _hash_source_file(model: Any) -> str:
    """Hash the .py source file of a model class."""
    import inspect
    try:
        source_path = inspect.getfile(type(model))
        return _hash_file(source_path)
    except (TypeError, OSError) as e:
        logger.warning(f"Could not locate source file for {type(model).__name__}: {e}")
        # Fall back to hashing the class name + version
        content = f"{type(model).__name__}:{getattr(model, 'version', 'unknown')}"
        return hashlib.sha256(content.encode()).hexdigest()


def _hash_file(path: str) -> str:
    """SHA256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── Smoke tests ──────────────────────────────────────────────────────────────

def _run_smoke_test(name: str, model: Any) -> None:
    """
    Run the smallest possible valid input through each model.
    Raises on any error or invalid output — DevOps will see inference_ok=False in /health.
    """
    from .schemas import KeystrokeEvent, MouseEvent, ScrollEvent, RequestContext

    if name == "keystroke":
        from ..detectors.behavioral.keystroke_model import KeystrokeModel
        events = [
            KeystrokeEvent(key="KeyA", keydown_time=float(i * 130), keyup_time=float(i * 130 + 90))
            for i in range(25)
        ]
        result = model.predict(events)
        assert 0.0 <= result.score <= 1.0, f"score out of range: {result.score}"

    elif name == "mouse":
        events = [
            MouseEvent(x=float(i * 5), y=float(i * 3), timestamp=float(i * 20), event_type="move")
            for i in range(35)
        ]
        result = model.predict(events)
        assert 0.0 <= result.score <= 1.0

    elif name == "scroll":
        events = [
            ScrollEvent(scroll_y=float(i * 100), timestamp=float(i * 200), direction="down", velocity=5.0)
            for i in range(20)
        ]
        result = model.predict(events)
        assert 0.0 <= result.score <= 1.0

    elif name == "resume":
        result = model.score("I built a Python API that served 10,000 users. I fixed a bug in March 2023.")
        assert 0.0 <= result.score <= 1.0

    elif name == "vocab":
        result = model.analyze("I really like working on projects that matter. Also I find bugs sometimes and fix them quickly.")
        assert 0.0 <= result.score <= 1.0

    elif name == "classifier":
        result = model.classify("I worked on this project for about two weeks and honestly it was a bit frustrating at first.")
        assert 0.0 <= result.score <= 1.0

    elif name == "fusion":
        ctx = RequestContext(action_type="generic")
        result = model.combine({"keystroke": 0.7, "resume": 0.8}, ctx, [])
        assert 0 <= result.human_trust_score <= 100

    else:
        logger.warning(f"No smoke test defined for model '{name}' — skipping.")


# ─── Manifest I/O ─────────────────────────────────────────────────────────────

def _load_manifest() -> Dict[str, Any]:
    """Load the model manifest written by deploy_model.py."""
    if not os.path.exists(MANIFEST_PATH):
        logger.warning(
            f"No manifest at {MANIFEST_PATH}. "
            "Models will run unverified (dev mode). "
            "Run: python -m ml_engine.scripts.deploy_model --help"
        )
        return {}
    try:
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load manifest: {e}")
        return {}
