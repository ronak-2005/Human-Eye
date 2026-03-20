"""
HumanEye ML Engine — Internal API (port 8001)
Only the backend service calls this. Never exposed to the internet.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import logging

from .schemas import (
    AnalyzeRequest, AnalyzeResponse,
    FaceAnalyzeRequest, FaceAnalyzeResponse,
    VoiceAnalyzeRequest, VoiceAnalyzeResponse,
    HealthResponse, ModelsResponse, ModelHealthEntry,
)
from ..detectors.behavioral.keystroke_model import KeystrokeModel
from ..detectors.behavioral.mouse_model import MouseModel
from ..detectors.behavioral.scroll_model import ScrollModel
from ..detectors.text.resume_scorer import ResumeScorer
from ..detectors.text.vocabulary_analyzer import VocabularyAnalyzer
from ..detectors.text.content_classifier import ContentClassifier
from ..fusion.score_combiner import ScoreCombiner
from ..model_registry import MODEL_REGISTRY, run_startup_smoke_tests

logger = logging.getLogger(__name__)

# Global model registry — loaded once at startup
models = {}
_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all models at startup, verify hashes, run smoke tests, then serve."""
    logger.info("Loading ML models...")
    models["keystroke"] = KeystrokeModel()
    models["mouse"] = MouseModel()
    models["scroll"] = ScrollModel()
    models["resume"] = ResumeScorer()
    models["vocab"] = VocabularyAnalyzer()
    models["classifier"] = ContentClassifier()
    models["fusion"] = ScoreCombiner()
    logger.info("All Phase 1 models instantiated.")

    # Verify hashes + run inference smoke tests — populates MODEL_REGISTRY
    run_startup_smoke_tests(models)
    logger.info("Startup smoke tests complete.")
    yield
    models.clear()
    logger.info("Models released.")


app = FastAPI(
    title="HumanEye ML Engine",
    version="1.0.0",
    description="Internal detection API. Not for external use.",
    lifespan=lifespan,
)

# Internal network only — allow backend service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://backend:8000", "http://localhost:8000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Core analysis endpoint. Receives signals from the backend,
    runs all available detectors, returns combined scores.

    Called by: backend/services/ml_client.py
    """
    start = time.perf_counter()
    scores = {}
    flags = []

    # --- Behavioral signals ---
    if req.signals.keystrokes:
        ks_result = models["keystroke"].predict(req.signals.keystrokes)
        scores["keystroke"] = ks_result.score
        flags.extend(ks_result.flags)

    if req.signals.mouse_events:
        ms_result = models["mouse"].predict(req.signals.mouse_events)
        scores["mouse"] = ms_result.score
        flags.extend(ms_result.flags)

    if req.signals.scroll_events:
        sc_result = models["scroll"].predict(req.signals.scroll_events)
        scores["scroll"] = sc_result.score
        flags.extend(sc_result.flags)

    # --- Text signals ---
    if req.signals.text_content:
        vocab_result = models["vocab"].analyze(req.signals.text_content)
        resume_result = models["resume"].score(req.signals.text_content)
        cls_result = models["classifier"].classify(req.signals.text_content)
        scores["vocabulary"] = vocab_result.score
        scores["resume"] = resume_result.score
        scores["classifier"] = cls_result.score
        flags.extend(vocab_result.flags + resume_result.flags + cls_result.flags)

    # --- Fusion ---
    if not scores:
        raise HTTPException(status_code=422, detail="No analyzable signals provided.")

    fusion_result = models["fusion"].combine(
        scores=scores,
        context=req.context,
        flags=flags,
    )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    return AnalyzeResponse(
        behavioral_score=scores.get("keystroke") or scores.get("mouse") or scores.get("scroll"),
        text_score=scores.get("resume") or scores.get("vocabulary"),
        combined_score=fusion_result.combined_score,
        human_trust_score=fusion_result.human_trust_score,
        flags=list(set(flags)),
        signal_scores=scores,
        confidence=fusion_result.confidence,
        processing_time_ms=elapsed_ms,
    )


@app.post("/analyze/face", response_model=FaceAnalyzeResponse)
async def analyze_face(req: FaceAnalyzeRequest) -> FaceAnalyzeResponse:
    """
    Phase 2: Face & liveness detection.
    rPPG blood flow + GAN detection + skin physics verification.
    Returns stub until Phase 2 models are implemented.
    """
    # Phase 2 stub — returns neutral score so backend is not blocked
    return FaceAnalyzeResponse(
        liveness_score=0.5,
        deepfake_probability=0.0,
        skin_physics_pass=None,
        rppg_bpm=None,
        asymmetry_score=None,
        flags=[],
        phase="stub_phase2",
    )


@app.post("/analyze/voice", response_model=VoiceAnalyzeResponse)
async def analyze_voice(req: VoiceAnalyzeRequest) -> VoiceAnalyzeResponse:
    """
    Phase 2: Voice forensics.
    Jitter/shimmer analysis + breathing architecture + clone detection.
    Returns stub until Phase 2 models are implemented.
    """
    return VoiceAnalyzeResponse(
        clone_probability=0.0,
        jitter_score=None,
        shimmer_score=None,
        breathing_natural=None,
        flags=[],
        phase="stub_phase2",
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """
    Health check consumed by:
    - Kubernetes liveness probe  → checks status != "starting"
    - Kubernetes readiness probe → checks phase1_ready == True
    - DevOps dashboards          → checks every model's inference_ok
    - Security audit             → checks every model's hash_verified
    - Backend ml_client.py       → checks phase1_ready before routing requests

    Response time target: < 50ms (no heavy computation here).
    """
    import torch
    import time as _time

    gpu_available = torch.cuda.is_available()
    gpu_memory = None
    if gpu_available:
        try:
            from .schemas import GpuMemoryInfo
            props = torch.cuda.get_device_properties(0)
            allocated = torch.cuda.memory_allocated(0) // (1024 * 1024)
            total = props.total_memory // (1024 * 1024)
            gpu_memory = GpuMemoryInfo(
                device_name=props.name,
                total_mb=total,
                allocated_mb=allocated,
                free_mb=total - allocated,
            )
        except Exception:
            pass

    # Build per-model health entries from the registry
    from ..model_registry import MODEL_REGISTRY
    model_entries = {}
    for name, model in models.items():
        reg = MODEL_REGISTRY.get(name, {})
        model_entries[name] = ModelHealthEntry(
            loaded=True,
            version=getattr(model, "version", "unknown"),
            mlflow_run_id=reg.get("mlflow_run_id"),
            sha256=reg.get("sha256"),
            hash_verified=reg.get("hash_verified", False),
            inference_ok=reg.get("inference_ok", False),
            last_trained=getattr(model, "last_trained", "unknown"),
        )

    phase1_models = {"keystroke", "mouse", "scroll", "resume", "vocab", "fusion"}
    phase1_ready = (
        phase1_models.issubset(set(models.keys()))
        and all(model_entries[m].hash_verified for m in phase1_models if m in model_entries)
    )

    status = "ok" if phase1_ready else ("starting" if not models else "degraded")

    return HealthResponse(
        status=status,
        phase1_ready=phase1_ready,
        phase2_ready=False,
        uptime_seconds=round(_time.time() - _startup_time, 1),
        models=model_entries,
        gpu_available=gpu_available,
        gpu_memory=gpu_memory,
        models_loaded=list(models.keys()),
    )


@app.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """Returns currently loaded models, versions and training metadata."""
    model_info = {}
    for name, model in models.items():
        model_info[name] = {
            "version": getattr(model, "version", "1.0.0"),
            "last_trained": getattr(model, "last_trained", "initial"),
            "accuracy": getattr(model, "accuracy", None),
        }
    return ModelsResponse(loaded_models=model_info)
