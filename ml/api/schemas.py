"""
Pydantic schemas for the ML Engine internal API.
These define the exact contract with the backend service.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ─── Shared signal types ────────────────────────────────────────────────────

class KeystrokeEvent(BaseModel):
    key: str = Field(..., description="Key code (e.g. 'KeyA'). NEVER the character value.")
    keydown_time: float = Field(..., description="Timestamp in ms when key was pressed")
    keyup_time: float = Field(..., description="Timestamp in ms when key was released")


class MouseEvent(BaseModel):
    x: float
    y: float
    timestamp: float
    event_type: str = Field(..., description="move | click | enter | leave")
    button: Optional[int] = None


class ScrollEvent(BaseModel):
    scroll_y: float
    timestamp: float
    direction: str = Field(..., description="up | down")
    velocity: float


class SignalsPayload(BaseModel):
    keystrokes: Optional[List[KeystrokeEvent]] = None
    mouse_events: Optional[List[MouseEvent]] = None
    scroll_events: Optional[List[ScrollEvent]] = None
    text_content: Optional[str] = Field(None, max_length=50000)
    video_frame_data: Optional[str] = Field(None, description="Base64 encoded frames — Phase 2")
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio — Phase 2")


class RequestContext(BaseModel):
    action_type: str = Field(..., description="job_application | review | exam | login | generic")
    platform_user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_duration_ms: Optional[float] = None


# ─── /analyze ───────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    session_id: str
    signals: SignalsPayload
    context: RequestContext


class AnalyzeResponse(BaseModel):
    behavioral_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    text_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    combined_score: float = Field(..., ge=0.0, le=1.0)
    human_trust_score: int = Field(..., ge=0, le=100)
    flags: List[str] = []
    signal_scores: Dict[str, float] = {}
    confidence: str = Field(..., description="high | medium | low")
    processing_time_ms: float


# ─── /analyze/face ──────────────────────────────────────────────────────────

class FaceAnalyzeRequest(BaseModel):
    session_id: str
    video_frames: List[str] = Field(..., description="List of base64 encoded JPEG frames")
    frame_rate: float = Field(30.0, description="Frames per second of input video")
    context: RequestContext


class FaceAnalyzeResponse(BaseModel):
    liveness_score: float = Field(..., ge=0.0, le=1.0)
    deepfake_probability: float = Field(..., ge=0.0, le=1.0)
    skin_physics_pass: Optional[bool] = None
    rppg_bpm: Optional[float] = None
    asymmetry_score: Optional[float] = None
    flags: List[str] = []
    phase: str = "production"


# ─── /analyze/voice ─────────────────────────────────────────────────────────

class VoiceAnalyzeRequest(BaseModel):
    session_id: str
    audio_data: str = Field(..., description="Base64 encoded WAV/PCM audio")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    context: RequestContext


class VoiceAnalyzeResponse(BaseModel):
    clone_probability: float = Field(..., ge=0.0, le=1.0)
    jitter_score: Optional[float] = None
    shimmer_score: Optional[float] = None
    breathing_natural: Optional[bool] = None
    flags: List[str] = []
    phase: str = "production"


# ─── /health & /models ──────────────────────────────────────────────────────

class ModelHealthEntry(BaseModel):
    """Per-model health info returned in /health. Used by DevOps probes."""
    loaded: bool
    version: str
    mlflow_run_id: Optional[str] = None   # Security: ties to MLflow audit trail
    sha256: Optional[str] = None           # Security: hash verified at load time
    hash_verified: bool = False            # Security: did the hash check pass?
    inference_ok: bool = False             # DevOps: did the smoke-test pass at startup?
    last_trained: str = "unknown"


class GpuMemoryInfo(BaseModel):
    """GPU memory stats. Populated only when gpu_available=True."""
    device_name: str
    total_mb: int
    allocated_mb: int
    free_mb: int


class HealthResponse(BaseModel):
    """
    Full health payload consumed by:
    - Kubernetes liveness + readiness probes (checks status + phase1_ready)
    - DevOps monitoring dashboards (checks all model entries)
    - Security audit (checks hash_verified on every model entry)
    - Backend /health passthrough (checks phase1_ready before routing traffic)
    """
    status: str                              # "ok" | "degraded" | "starting"
    phase1_ready: bool                       # All Phase 1 models loaded + hash verified
    phase2_ready: bool                       # Face + voice models ready
    uptime_seconds: float
    models: Dict[str, ModelHealthEntry]      # One entry per loaded model
    gpu_available: bool
    gpu_memory: Optional[GpuMemoryInfo] = None
    # Simple list kept for backwards compat with backend ml_client.py
    models_loaded: List[str] = []


class ModelsResponse(BaseModel):
    loaded_models: Dict[str, Any]


# ─── Internal result types used by detectors ────────────────────────────────

class DetectorResult(BaseModel):
    """Returned by every detector's predict() method."""
    score: float = Field(..., ge=0.0, le=1.0, description="0=bot, 1=human")
    flags: List[str] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_features: Optional[Dict[str, float]] = None
