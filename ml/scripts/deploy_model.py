"""
HumanEye ML Engine — Model Deploy Script
Security gate that MUST run before every production model deployment.

What this script does:
  1. Computes SHA256 hash of the model file (or source file for stat-only models)
  2. Logs the model to MLflow with name, version, hash, and deployer identity
  3. Writes/updates saved_models/manifest.json (consumed by model_registry.py at startup)
  4. Prints a deployment receipt that Security logs in their audit trail

NOTHING goes to production without a manifest.json entry.
The model_registry.py startup check will refuse to mark hash_verified=True
for any model not in the manifest.

Usage:
  # Register all Phase 1 stat-only models (run once after code changes)
  python -m ml_engine.scripts.deploy_model --all-phase1

  # Register a specific neural model file
  python -m ml_engine.scripts.deploy_model --model rppg --file saved_models/rppg_v1.onnx

  # Show current manifest
  python -m ml_engine.scripts.deploy_model --status
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MANIFEST_PATH = os.environ.get(
    "MODEL_MANIFEST_PATH",
    str(Path(__file__).parent.parent / "saved_models" / "manifest.json"),
)

MLFLOW_URI = os.environ.get("ML_TRACKING_URI", "http://mlflow:5000")

# Phase 1 stat-only models and their source files
PHASE1_SOURCE_MAP = {
    "keystroke":   "ml_engine/detectors/behavioral/keystroke_model.py",
    "mouse":       "ml_engine/detectors/behavioral/mouse_model.py",
    "scroll":      "ml_engine/detectors/behavioral/scroll_model.py",
    "resume":      "ml_engine/detectors/text/resume_scorer.py",
    "vocab":       "ml_engine/detectors/text/vocabulary_analyzer.py",
    "classifier":  "ml_engine/detectors/text/content_classifier.py",
    "fusion":      "ml_engine/fusion/score_combiner.py",
}


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def log_to_mlflow(
    model_name: str,
    version: str,
    sha256: str,
    file_path: str,
    deployer: str,
) -> Optional[str]:
    """
    Log model metadata to MLflow. Returns run_id on success, None on failure.
    Service still works if MLflow is down — manifest.json is the source of truth.
    """
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment("humaneye-model-registry")

        with mlflow.start_run(run_name=f"deploy_{model_name}_{version}") as run:
            mlflow.log_params({
                "model_name": model_name,
                "version": version,
                "deployer": deployer,
                "file_path": file_path,
                "deploy_timestamp": datetime.now(timezone.utc).isoformat(),
            })
            mlflow.log_metrics({"sha256_logged": 1.0})
            mlflow.set_tags({
                "sha256": sha256,
                "deploy_type": "stat_model" if file_path.endswith(".py") else "neural_model",
                "environment": os.environ.get("ENVIRONMENT", "development"),
            })
            run_id = run.info.run_id
            logger.info(f"MLflow run logged: {run_id}")
            return run_id

    except Exception as e:
        logger.warning(f"MLflow logging failed (non-fatal): {e}")
        return None


def register_model(
    name: str,
    file_path: str,
    version: str,
    deployer: str,
) -> dict:
    """Core registration logic. Returns the manifest entry dict."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Model file not found: {file_path}")

    sha256 = hash_file(file_path)
    run_id = log_to_mlflow(name, version, sha256, file_path, deployer)

    entry = {
        "model_name": name,
        "version": version,
        "sha256": sha256,
        "mlflow_run_id": run_id,
        "file_path": file_path,
        "deployer": deployer,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    return entry


def update_manifest(name: str, entry: dict) -> None:
    """Write/update manifest.json with the new model entry."""
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)

    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    manifest[name] = entry

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Manifest updated: {MANIFEST_PATH}")


def print_receipt(entry: dict) -> None:
    """Print the deployment receipt for Security's audit log."""
    print("\n" + "=" * 60)
    print("  HUMANEYE MODEL DEPLOYMENT RECEIPT")
    print("  Copy this to your Security audit log.")
    print("=" * 60)
    print(f"  Model name:      {entry['model_name']}")
    print(f"  Version:         {entry['version']}")
    print(f"  SHA256:          {entry['sha256']}")
    print(f"  MLflow run ID:   {entry['mlflow_run_id'] or 'NOT LOGGED (MLflow unavailable)'}")
    print(f"  Registered at:   {entry['registered_at']}")
    print(f"  Deployer:        {entry['deployer']}")
    print(f"  Source file:     {entry['file_path']}")
    print("=" * 60)
    print("  VERIFY: GET http://ml-engine:8001/health")
    print("  Expect: models.<name>.hash_verified == true")
    print("=" * 60 + "\n")


def cmd_all_phase1(deployer: str) -> None:
    """Register all Phase 1 statistical models from their source files."""
    print(f"\nRegistering all Phase 1 models as deployer: {deployer}\n")
    for name, rel_path in PHASE1_SOURCE_MAP.items():
        # Resolve relative to repo root
        abs_path = str(Path(__file__).parent.parent.parent / rel_path)
        try:
            # Read version from module
            version = "1.0.0"
            entry = register_model(name, abs_path, version, deployer)
            update_manifest(name, entry)
            print_receipt(entry)
        except FileNotFoundError as e:
            print(f"  SKIP {name}: {e}")


def cmd_single_model(name: str, file_path: str, version: str, deployer: str) -> None:
    """Register a single model (used for neural .onnx models in Phase 2)."""
    entry = register_model(name, file_path, version, deployer)
    update_manifest(name, entry)
    print_receipt(entry)


def cmd_status() -> None:
    """Print current manifest status."""
    if not os.path.exists(MANIFEST_PATH):
        print(f"\nNo manifest found at {MANIFEST_PATH}")
        print("Run: python -m ml_engine.scripts.deploy_model --all-phase1\n")
        return

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    print(f"\nManifest: {MANIFEST_PATH}")
    print(f"Models registered: {len(manifest)}\n")
    print(f"{'Model':<14} {'Version':<10} {'SHA256 (first 16)':<18} {'MLflow Run ID':<36} {'Registered At'}")
    print("-" * 100)
    for name, entry in manifest.items():
        sha_short = entry.get("sha256", "none")[:16] + "..."
        run_id = entry.get("mlflow_run_id") or "not logged"
        print(f"{name:<14} {entry.get('version','?'):<10} {sha_short:<18} {run_id:<36} {entry.get('registered_at','?')}")
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="HumanEye model deploy — Security gate for production deployments"
    )
    parser.add_argument(
        "--all-phase1",
        action="store_true",
        help="Register all Phase 1 statistical models",
    )
    parser.add_argument("--model", help="Model name (e.g. rppg)")
    parser.add_argument("--file", help="Path to .onnx or .pt file")
    parser.add_argument("--version", default="1.0.0", help="Model version string")
    parser.add_argument(
        "--deployer",
        default=os.environ.get("USER", "unknown"),
        help="Your name/identity for the audit trail",
    )
    parser.add_argument("--status", action="store_true", help="Show current manifest")

    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.all_phase1:
        cmd_all_phase1(args.deployer)
    elif args.model and args.file:
        cmd_single_model(args.model, args.file, args.version, args.deployer)
    else:
        parser.print_help()
        sys.exit(1)
