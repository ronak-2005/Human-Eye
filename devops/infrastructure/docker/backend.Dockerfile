# ============================================================
# HumanEye — Backend Dockerfile (FastAPI)
# Multi-stage: development (hot reload) + production (gunicorn)
# ============================================================

# ── Base ──────────────────────────────────────────────────
FROM python:3.11-slim AS base
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ── Development (hot reload with uvicorn) ─────────────────
FROM base AS development
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
COPY backend/ ./backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────────
FROM base AS production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
COPY backend/ ./backend/

# Non-root user for security
RUN groupadd -r humaneye && useradd -r -g humaneye humaneye
RUN chown -R humaneye:humaneye /app
USER humaneye

# Gunicorn with uvicorn workers: 2 workers per CPU + 1
CMD ["gunicorn", "backend.main:app", \
     "-w", "3", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--keepalive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1
