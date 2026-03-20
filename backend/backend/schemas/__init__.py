from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
from datetime import datetime


class ErrorResponse(BaseModel):
    error: str
    message: str
    code: str


# ── Signals (from Browser/Mobile SDK) ────────────────────────────────────────

class KeystrokeEvent(BaseModel):
    key: str
    keydown_time: float   # ms relative to session start
    keyup_time: float

class MouseEvent(BaseModel):
    x: float
    y: float
    timestamp: float
    event_type: str       # move | click | enter | leave
    button: Optional[int] = None

class ScrollEvent(BaseModel):
    scroll_y: float
    timestamp: float
    direction: str        # up | down
    velocity: float

class SignalPayload(BaseModel):
    keystrokes:       Optional[List[KeystrokeEvent]] = Field(default_factory=list)
    mouse_events:     Optional[List[MouseEvent]]     = Field(default_factory=list)
    scroll_events:    Optional[List[ScrollEvent]]    = Field(default_factory=list)
    text_content:     Optional[str]                  = Field(None, max_length=50000)
    video_frame_data: Optional[List[str]]            = None  # Phase 2 — base64 JPEGs
    audio_data:       Optional[str]                  = None  # Phase 2 — base64 WAV

class RequestContext(BaseModel):
    action_type:         str  # job_application|review|exam|login|generic
    platform_user_id:    str
    ip_address:          Optional[str] = None
    user_agent:          Optional[str] = None
    session_duration_ms: Optional[int] = None


# ── POST /verify ──────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    session_id: str
    signals:    SignalPayload
    context:    RequestContext

class VerifyResponse(BaseModel):
    verification_id:    str
    human_trust_score:  Optional[int] = Field(None, ge=0, le=100)
    verdict:            str   # human|likely_human|uncertain|suspicious|synthetic|unavailable
    confidence:         str   # high|medium|low|none
    flags:              List[str]  = Field(default_factory=list)
    processing_time_ms: int
    signals_analyzed:   List[str]  = Field(default_factory=list)
    # Phase 2 fields — null in Phase 1
    liveness_score:       Optional[float] = None
    deepfake_probability: Optional[float] = None
    clone_probability:    Optional[float] = None


# ── POST /signals ─────────────────────────────────────────────────────────────

class SignalIngestRequest(BaseModel):
    session_id: str
    events:     List[dict]
    event_type: str       # keystroke | mouse | scroll
    timestamp:  datetime

class SignalIngestResponse(BaseModel):
    accepted:   int
    session_id: str


# ── GET /verifications ────────────────────────────────────────────────────────

class VerificationDetail(BaseModel):
    id:                 str
    session_id:         str
    human_trust_score:  Optional[int]
    verdict:            Optional[str]
    confidence:         Optional[str]
    flags:              List[str]
    signals_analyzed:   List[str]
    action_type:        Optional[str]
    platform_user_id:   Optional[str]
    status:             str
    processing_time_ms: Optional[int]
    created_at:         datetime
    completed_at:       Optional[datetime]
    class Config:
        from_attributes = True

class VerificationListResponse(BaseModel):
    verifications: List[VerificationDetail]
    total:         int
    page:          int
    page_size:     int


# ── GET /scores ───────────────────────────────────────────────────────────────

class ScoreResponse(BaseModel):
    platform_user_id:   str
    current_score:      float
    verification_count: int
    last_verified_at:   Optional[datetime]
    verdict:            str


# ── POST /webhooks/register ───────────────────────────────────────────────────

class WebhookRegisterRequest(BaseModel):
    url:    str
    secret: Optional[str] = None

    @validator("url")
    def url_must_be_https(cls, v):
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v

class WebhookRegisterResponse(BaseModel):
    id:         str
    url:        str
    is_active:  bool
    created_at: datetime


# ── /keys ─────────────────────────────────────────────────────────────────────

class KeyCreateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)

class KeyCreateResponse(BaseModel):
    id:         str
    api_key:    str   # plaintext — shown once only
    name:       Optional[str]
    created_at: datetime
    warning:    str = "Store this key securely. It will not be shown again."

class KeyRevokeResponse(BaseModel):
    id:         str
    revoked:    bool
    revoked_at: datetime

class KeyListItem(BaseModel):
    id:          str
    name:        Optional[str]
    is_active:   bool
    created_at:  datetime
    last_used_at: Optional[datetime]


# ── GET /health ───────────────────────────────────────────────────────────────

class MLEngineHealth(BaseModel):
    status:       str
    phase1_ready: bool
    phase2_ready: bool

class HealthResponse(BaseModel):
    status:     str   # ok | degraded
    version:    str   = "1.0.0"
    ml_engine:  MLEngineHealth
    database:   str
    redis:      str
