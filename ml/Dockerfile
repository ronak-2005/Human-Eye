# HumanEye ML Engine — Dockerfile
# Phase 1: CPU-only (behavioral + text detectors)
# Phase 2: Switch to nvidia/cuda base image for face/voice models

FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (layer caching)
COPY ml_engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY ml_engine/ ./ml_engine/

# Pre-download HuggingFace models at build time (not at runtime)
# Comment out if bandwidth-constrained during development
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='distilroberta-base')" || true

EXPOSE 8001

CMD ["uvicorn", "ml_engine.api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
