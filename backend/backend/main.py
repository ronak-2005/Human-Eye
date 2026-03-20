"""
HumanEye Backend — FastAPI Application Entry Point
Middleware registration order follows Security spec (FastAPI reverses order).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from core.database import init_db
from core.middleware import (
    PayloadSizeMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from api.v1 import (
    verify_router,
    signals_router,
    scores_router,
    webhooks_router,
    keys_router,
    health_router,
    metrics_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HumanEye backend starting — env=%s", settings.APP_ENV)
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("HumanEye backend shutting down.")


app = FastAPI(
    title="HumanEye API",
    description="Human Verification Infrastructure for the AI Age",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware (Security spec order — FastAPI reverses, so register reversed) ─
# Execution order: PayloadSize → RequestId → SecurityHeaders → CORS → Timing

app.add_middleware(TimingMiddleware)           # outermost — runs last
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PayloadSizeMiddleware)      # innermost — runs first

# ── Prometheus instrumentation (DevOps Week 2) ────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    logger.warning("prometheus_fastapi_instrumentator not installed — /metrics stub only")

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health_router,   prefix="/api/v1", tags=["health"])
app.include_router(verify_router,   prefix="/api/v1", tags=["verify"])
app.include_router(signals_router,  prefix="/api/v1", tags=["signals"])
app.include_router(scores_router,   prefix="/api/v1", tags=["scores"])
app.include_router(webhooks_router, prefix="/api/v1", tags=["webhooks"])
app.include_router(keys_router,     prefix="/api/v1", tags=["keys"])
app.include_router(metrics_router,  prefix="/api/v1", tags=["metrics"])
