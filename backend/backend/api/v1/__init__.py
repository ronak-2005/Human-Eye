"""
HumanEye — All API Route Handlers
Endpoints: /verify /signals /scores /verifications /webhooks /keys /health /metrics
Security rules enforced:
  - Every protected route: Depends(get_authenticated_customer)
  - Tenant isolation: always filter by customer_id
  - Cross-tenant: 404 not 403
  - make_request_log() for every inbound log
"""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import uuid as _uuid
import logging

from core.database import get_db
from core.auth import get_authenticated_customer
from core.rate_limit import check_rate_limit
from core.errors import not_found, bad_request
from core.security import generate_api_key, make_request_log
from core.webhook_validator import validate_webhook_url
from models.api_key import APIKey
from models.verification import Verification
from models.score import Score
from models.webhook import WebhookEndpoint
from services.ml_client import get_ml_client
from services.verification_service import run_verification, score_to_verdict
from schemas import (
    VerifyRequest, VerifyResponse,
    SignalIngestRequest, SignalIngestResponse,
    VerificationDetail, VerificationListResponse,
    ScoreResponse,
    WebhookRegisterRequest, WebhookRegisterResponse,
    KeyCreateRequest, KeyCreateResponse, KeyRevokeResponse, KeyListItem,
    HealthResponse, MLEngineHealth,
)

logger = logging.getLogger(__name__)

# ── Auth + rate limit combined dependency ─────────────────────────────────────

async def authenticated(
    request: Request,
    api_key: APIKey = Depends(get_authenticated_customer),
) -> APIKey:
    await check_rate_limit(str(api_key.id))
    return api_key


# ═════════════════════════════════════════════════════════════════════════════
# POST /api/v1/verify  — MOST IMPORTANT ENDPOINT
# ═════════════════════════════════════════════════════════════════════════════

verify_router = APIRouter()


@verify_router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Run human verification",
    description="""
Receives behavioral signals from the SDK, runs the 5-layer detection pipeline,
returns a Human Trust Score (0-100).

**Score ranges:**
- 80-100 → human (permit immediately)
- 65-79  → likely_human (permit with monitoring)
- 50-64  → uncertain (challenge required)
- 25-49  → suspicious (elevated challenge + review queue)
- 0-24   → synthetic (block + flag)
- null   → unavailable (ML engine down — do not block, flag for review)

**Phase 2:** Include `video_frame_data` for face/liveness detection,
`audio_data` for voice clone detection.
    """,
)
async def verify_human(
    body: VerifyRequest,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    logger.info("verify_request", extra=make_request_log(
        session_id=body.session_id,
        customer_id=str(api_key.user_id),
        path="/api/v1/verify",
    ))
    ml = get_ml_client()
    return await run_verification(
        request=body,
        customer_id=api_key.user_id,
        api_key_id=api_key.id,
        db=db,
        ml=ml,
    )


# ═════════════════════════════════════════════════════════════════════════════
# POST /api/v1/signals  — raw signal ingestion from SDK
# ═════════════════════════════════════════════════════════════════════════════

signals_router = APIRouter()


@signals_router.post(
    "/signals",
    response_model=SignalIngestResponse,
    summary="Ingest raw behavioral signals",
    description="SDK streams keystroke/mouse/scroll events. Stored in TimescaleDB for ML.",
)
async def ingest_signals(
    body: SignalIngestRequest,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    # NEVER log body.events — only metadata
    logger.info("signals_ingest", extra=make_request_log(
        session_id=body.session_id,
        customer_id=str(api_key.user_id),
        path="/api/v1/signals",
        event_count=len(body.events),
        event_type=body.event_type,
    ))

    # Store in TimescaleDB via raw SQL (ORM not used for hypertables)
    from core.database import get_ts_db
    from sqlalchemy import text
    ts_db_gen = get_ts_db()
    ts_db = await ts_db_gen.__anext__()
    try:
        table_map = {
            "keystroke": "keystroke_events",
            "mouse":     "mouse_events",
            "scroll":    "scroll_events",
        }
        table = table_map.get(body.event_type)
        if table:
            for event in body.events:
                event["session_id"] = body.session_id
                cols = ", ".join(event.keys())
                vals = ", ".join(f":{k}" for k in event.keys())
                await ts_db.execute(text(f"INSERT INTO {table} ({cols}, ts) VALUES ({vals}, NOW())"), event)
            await ts_db.commit()
    finally:
        await ts_db.close()

    return SignalIngestResponse(accepted=len(body.events), session_id=body.session_id)


# ═════════════════════════════════════════════════════════════════════════════
# GET /api/v1/verifications  &  GET /api/v1/verifications/{id}
# GET /api/v1/scores/{platform_user_id}
# ═════════════════════════════════════════════════════════════════════════════

scores_router = APIRouter()


def _verdict_from_score(score: float) -> str:
    if score >= 80: return "human"
    if score >= 65: return "likely_human"
    if score >= 50: return "uncertain"
    if score >= 25: return "suspicious"
    return "synthetic"


@scores_router.get(
    "/scores/{platform_user_id}",
    response_model=ScoreResponse,
    summary="Get persistent trust score for a platform user",
)
async def get_score(
    platform_user_id: str,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Score).where(
            Score.user_id == api_key.user_id,          # tenant isolation
            Score.platform_user_id == platform_user_id,
        )
    )
    score = result.scalar_one_or_none()
    if not score:
        not_found("Score")   # 404 — not 403

    return ScoreResponse(
        platform_user_id=score.platform_user_id,
        current_score=score.current_score,
        verification_count=score.verification_count,
        last_verified_at=score.last_verified_at,
        verdict=_verdict_from_score(score.current_score),
    )


@scores_router.get(
    "/verifications/{verification_id}",
    response_model=VerificationDetail,
    summary="Get a single verification",
)
async def get_verification(
    verification_id: str,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    try:
        vid = _uuid.UUID(verification_id)
    except ValueError:
        bad_request("Invalid verification ID")

    result = await db.execute(
        select(Verification).where(
            Verification.id == vid,
            Verification.user_id == api_key.user_id,   # tenant isolation
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        not_found("Verification")   # 404 — not 403

    return VerificationDetail(
        id=str(v.id), session_id=v.session_id,
        human_trust_score=v.human_trust_score,
        verdict=v.verdict, confidence=v.confidence,
        flags=v.flags or [], signals_analyzed=v.signals_analyzed or [],
        action_type=v.action_type, platform_user_id=v.platform_user_id,
        status=v.status, processing_time_ms=v.processing_time_ms,
        created_at=v.created_at, completed_at=v.completed_at,
    )


@scores_router.get(
    "/verifications",
    response_model=VerificationListResponse,
    summary="List all verifications",
)
async def list_verifications(
    page:      int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    total = (await db.execute(
        select(func.count()).select_from(Verification)
        .where(Verification.user_id == api_key.user_id)
    )).scalar()

    rows = (await db.execute(
        select(Verification)
        .where(Verification.user_id == api_key.user_id)
        .order_by(Verification.created_at.desc())
        .offset(offset).limit(page_size)
    )).scalars().all()

    return VerificationListResponse(
        verifications=[
            VerificationDetail(
                id=str(v.id), session_id=v.session_id,
                human_trust_score=v.human_trust_score,
                verdict=v.verdict, confidence=v.confidence,
                flags=v.flags or [], signals_analyzed=v.signals_analyzed or [],
                action_type=v.action_type, platform_user_id=v.platform_user_id,
                status=v.status, processing_time_ms=v.processing_time_ms,
                created_at=v.created_at, completed_at=v.completed_at,
            ) for v in rows
        ],
        total=total, page=page, page_size=page_size,
    )


# ═════════════════════════════════════════════════════════════════════════════
# POST /api/v1/webhooks/register
# ═════════════════════════════════════════════════════════════════════════════

webhooks_router = APIRouter()


@webhooks_router.post(
    "/webhooks/register",
    response_model=WebhookRegisterResponse,
    summary="Register a webhook endpoint",
)
async def register_webhook(
    body: WebhookRegisterRequest,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    validate_webhook_url(body.url)   # security check
    endpoint = WebhookEndpoint(
        user_id=api_key.user_id,
        url=body.url,
        secret=body.secret,
        is_active=True,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return WebhookRegisterResponse(
        id=str(endpoint.id), url=endpoint.url,
        is_active=endpoint.is_active, created_at=endpoint.created_at,
    )


# ═════════════════════════════════════════════════════════════════════════════
# POST /api/v1/keys  &  DELETE /api/v1/keys/{id}  &  GET /api/v1/keys
# ═════════════════════════════════════════════════════════════════════════════

keys_router = APIRouter()


@keys_router.post("/keys", response_model=KeyCreateResponse, status_code=201,
                  summary="Generate a new API key")
async def create_key(
    body: KeyCreateRequest,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    plaintext, hashed = generate_api_key()
    new_key = APIKey(user_id=api_key.user_id, key_hash=hashed, name=body.name, is_active=True)
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return KeyCreateResponse(
        id=str(new_key.id), api_key=plaintext,
        name=new_key.name, created_at=new_key.created_at,
    )


@keys_router.get("/keys", response_model=list[KeyListItem],
                 summary="List all API keys for this account")
async def list_keys(
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey).where(
            APIKey.user_id == api_key.user_id,
            APIKey.is_active == True,           # noqa: E712
        ).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        KeyListItem(id=str(k.id), name=k.name, is_active=k.is_active,
                    created_at=k.created_at, last_used_at=k.last_used_at)
        for k in keys
    ]


@keys_router.delete("/keys/{key_id}", response_model=KeyRevokeResponse,
                    summary="Revoke an API key")
async def revoke_key(
    key_id: str,
    api_key: APIKey = Depends(authenticated),
    db: AsyncSession = Depends(get_db),
):
    try:
        kid = _uuid.UUID(key_id)
    except ValueError:
        bad_request("Invalid key ID")

    result = await db.execute(
        select(APIKey).where(
            APIKey.id == kid,
            APIKey.user_id == api_key.user_id,  # tenant isolation
            APIKey.is_active == True,            # noqa: E712
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        not_found("API key")   # 404 — not 403

    record.is_active  = False
    record.revoked_at = datetime.utcnow()
    await db.commit()
    return KeyRevokeResponse(id=str(record.id), revoked=True, revoked_at=record.revoked_at)


# ═════════════════════════════════════════════════════════════════════════════
# GET /api/v1/health  — DevOps health check format exactly
# ═════════════════════════════════════════════════════════════════════════════

health_router = APIRouter()


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Used by ALB, ECS, Kubernetes liveness/readiness probes, and CI smoke test.",
)
async def health_check(db: AsyncSession = Depends(get_db)):
    import redis.asyncio as aioredis
    from core.config import settings

    db_status    = "ok"
    redis_status = "ok"

    try:
        await db.execute(select(func.now()))
    except Exception:
        db_status = "error"

    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception:
        redis_status = "error"

    ml = get_ml_client()
    ml_health = await ml.health()

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        version="1.0.0",
        ml_engine=MLEngineHealth(
            status=ml_health.get("status", "unknown"),
            phase1_ready=ml_health.get("phase1_ready", False),
            phase2_ready=ml_health.get("phase2_ready", False),
        ),
        database=db_status,
        redis=redis_status,
    )


# ═════════════════════════════════════════════════════════════════════════════
# GET /metrics  — Prometheus format (DevOps Week 2 requirement)
# ═════════════════════════════════════════════════════════════════════════════

metrics_router = APIRouter()


@metrics_router.get("/metrics", response_class=PlainTextResponse,
                    include_in_schema=False)
async def metrics():
    """
    Prometheus metrics endpoint.
    Full metrics via prometheus-fastapi-instrumentator (registered in main.py).
    This stub ensures the endpoint exists immediately.
    """
    return PlainTextResponse(
        "# HumanEye metrics — auto-instrumented by prometheus-fastapi-instrumentator\n"
        "# See /metrics for full output after instrumentator initializes.\n",
        media_type="text/plain; version=0.0.4",
    )
