# HumanEye — ML Engine

Detection intelligence for the HumanEye human verification platform.
Internal service running on port 8001. Not exposed to the internet.

---

## Quick Start (Local Development)

```bash
# From repo root
docker-compose up ml_engine mlflow

# Or run directly
cd ml_engine
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

API docs available at: http://localhost:8001/docs

---

## Phase Status

| Component | Status | Notes |
|---|---|---|
| Keystroke model | ✅ Phase 1 | Statistical features, ready for pilot |
| Mouse model | ✅ Phase 1 | Path + tremor analysis |
| Scroll model | ✅ Phase 1 | Backscroll + pause detection |
| Vocabulary analyzer | ✅ Phase 1 | Human Imperfection Index |
| Resume scorer | ✅ Phase 1 | Specificity + buzzword detection |
| Content classifier | ✅ Phase 1 | Statistical + HuggingFace blend |
| Fusion engine | ✅ Phase 1 | Context-aware weighted fusion |
| rPPG detector | 🔲 Phase 2 | Stub only — requires MediaPipe + OpenCV |
| GAN detector | 🔲 Phase 2 | Stub only |
| Skin physics | 🔲 Phase 2 | Stub only — most novel detector |
| Voice forensics | 🔲 Phase 2 | Stub only — requires Librosa |

---

## File Structure

```
ml_engine/
├── api/
│   ├── main.py             ← FastAPI app, routes, lifespan
│   └── schemas.py          ← All Pydantic request/response types
├── detectors/
│   ├── behavioral/
│   │   ├── keystroke_model.py
│   │   ├── mouse_model.py
│   │   └── scroll_model.py
│   ├── text/
│   │   ├── vocabulary_analyzer.py
│   │   ├── resume_scorer.py
│   │   └── content_classifier.py
│   ├── face/               ← Phase 2 stubs
│   │   ├── rppg_detector.py
│   │   ├── gan_detector.py
│   │   └── skin_physics.py
│   └── voice/              ← Phase 2 stubs
│       ├── jitter_analyzer.py
│       └── clone_detector.py
├── fusion/
│   └── score_combiner.py   ← Cross-signal fusion engine
├── preprocessing/
│   └── signal_cleaner.py   ← Raw signal validation + normalization
├── training/
│   └── train_behavioral.py ← Synthetic data generation
├── evaluation/
│   └── model_evaluator.py  ← Accuracy testing framework
├── tests/
│   └── test_all.py         ← Full test suite
├── saved_models/           ← .pt and .onnx model files (gitignored)
├── API_CONTRACTS.md        ← What every other team must deliver
├── requirements.txt
└── Dockerfile
```

---

## Running Tests

```bash
pytest ml_engine/tests/ -v
```

All tests use synthetic data — no external dependencies or GPU needed.

---

## Key Design Decisions

**Why not use a single neural network?**
Each detector is a specialized module. This means:
- You can debug which signal triggered a flag
- You can improve one detector without retraining others
- The fusion engine's weights are interpretable

**Why ONNX Runtime in production?**
PyTorch is used for training. Models are exported to ONNX format for production.
ONNX inference is 2–5x faster than PyTorch inference on CPU.

**Why is Phase 2 stubbed instead of not implemented?**
The API contract is fixed. Backend can call /analyze/face and /analyze/voice today
and get neutral scores. When Phase 2 is ready, we swap the implementation —
the backend code changes zero lines.

---

## Adding a New Detector

1. Create `ml_engine/detectors/<category>/<name>_model.py`
2. Implement `predict(input) → DetectorResult`
3. Load it in `api/main.py` lifespan
4. Add it to `fusion/score_combiner.py` BASE_WEIGHTS
5. Add tests in `tests/test_all.py`
6. Update API_CONTRACTS.md if the input schema changes

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ML_ENGINE_PORT` | `8001` | Port to listen on |
| `ML_TRACKING_URI` | `http://mlflow:5000` | MLflow tracking server |
| `MODEL_DIR` | `./saved_models` | Path to trained model files |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENVIRONMENT` | `development` | development / staging / production |
