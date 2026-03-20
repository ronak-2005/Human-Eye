# ============================================================
# HumanEye — ML Engine Dockerfile (PyTorch)
# Phase 1 : CPU-only  (2 vCPU / 4 GB req  →  4 vCPU / 8 GB limit)
# Phase 2 : GPU       (g4dn.xlarge — NVIDIA T4, uncomment section)
#
# ML engineer requirements honoured:
#   • ML_ENGINE_PORT=8001          (internal only, never internet-facing)
#   • ML_ENGINE_WORKERS=2          (scale up in Phase 2)
#   • TRANSFORMERS_CACHE=/app/.cache/huggingface
#   • MODEL_DIR=/app/ml_engine/saved_models  (persistent volume mount point)
#   • startup ~30s → initialDelaySeconds=45 in k8s liveness probe
#   • structured JSON logging to stdout → CloudWatch ships it
# ============================================================

# ── Phase 1 Base (CPU) ────────────────────────────────────
FROM python:3.11-slim AS base-cpu
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY ml_engine/requirements.txt ./ml_engine/requirements.txt
RUN pip install --no-cache-dir -r ml_engine/requirements.txt

# Pre-create all directories that need to exist at container start
RUN mkdir -p \
    /app/ml_engine/saved_models \
    /app/.cache/huggingface \
    /app/ml_engine/saved_models/.torch_cache

# ── Phase 2 Base (GPU — uncomment entire block when Phase 2 starts) ──────
# FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS base-gpu
# WORKDIR /app
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     python3.11 python3-pip python3.11-dev \
#     curl gcc libpq-dev libglib2.0-0 libsm6 libxext6 ffmpeg \
#     && rm -rf /var/lib/apt/lists/*
# COPY ml_engine/requirements-gpu.txt ./ml_engine/requirements.txt
# RUN pip3 install --no-cache-dir -r ml_engine/requirements.txt
# RUN mkdir -p /app/ml_engine/saved_models /app/.cache/huggingface

# ── Development (hot reload, GPU passthrough if developer has it) ─────────
FROM base-cpu AS development
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ML engineer-specified env vars (overridable via docker-compose .env)
ENV ML_ENGINE_PORT=8001
ENV ML_ENGINE_WORKERS=2
ENV ML_TRACKING_URI=http://mlflow:5000
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV MODEL_DIR=/app/ml_engine/saved_models
ENV TORCH_HOME=/app/ml_engine/saved_models/.torch_cache
ENV LOG_LEVEL=INFO
ENV ENVIRONMENT=development

COPY ml_engine/ ./ml_engine/

# Development: hot reload, single worker
CMD ["uvicorn", "ml_engine.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--reload", \
     "--log-level", "info"]

# ── Production ────────────────────────────────────────────
FROM base-cpu AS production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ML engineer-specified env vars — production values
ENV ML_ENGINE_PORT=8001
ENV ML_ENGINE_WORKERS=2
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV MODEL_DIR=/app/ml_engine/saved_models
ENV TORCH_HOME=/app/ml_engine/saved_models/.torch_cache
ENV LOG_LEVEL=INFO
ENV ENVIRONMENT=production

# Non-root user
RUN groupadd -r humaneye && useradd -r -g humaneye humaneye
COPY ml_engine/ ./ml_engine/
RUN chown -R humaneye:humaneye /app /app/.cache
USER humaneye

# ML_ENGINE_WORKERS=2 (Phase 1 CPU), bump to 4 in Phase 2 GPU
# timeout=120 because HuggingFace inference can take up to ~80ms
CMD ["gunicorn", "ml_engine.api:app", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8001", \
     "--timeout", "120", \
     "--log-level", "info", \
     "--access-logformat", "{\"time\":\"%(t)s\",\"method\":\"%(m)s\",\"path\":\"%(U)s\",\"status\":%(s)s,\"duration_ms\":%(D)s}"]

EXPOSE 8001

# initialDelaySeconds=45 in k8s (models take ~30s to load)
# Here we use 40s start period to match
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
  CMD curl -f http://localhost:8001/health || exit 1
