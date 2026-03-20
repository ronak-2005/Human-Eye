# HumanEye ML Engine — GPU Memory Requirements
# For DevOps: use this to pick the right g4dn instance size for Phase 2.
# Written by: ML Engineer
# Last updated: Phase 1 complete, Phase 2 planning

=============================================================
 PHASE 1 — NO GPU REQUIRED
=============================================================

All Phase 1 models are statistical/rule-based or use CPU-only transformers.
Run on any ECS Fargate task or EC2 instance with sufficient RAM.

  Model              Type              GPU Memory    RAM needed
  ─────────────────────────────────────────────────────────────
  keystroke_model    Statistical        0 MB          ~10 MB
  mouse_model        Statistical        0 MB          ~10 MB
  scroll_model       Statistical        0 MB          ~10 MB
  vocabulary_analyzer Statistical       0 MB          ~20 MB
  resume_scorer      Statistical        0 MB          ~15 MB
  content_classifier HuggingFace CPU    0 MB          ~500 MB *
  fusion/score_combiner Statistical     0 MB          ~5 MB

  * distilroberta-base loaded in CPU mode: ~500 MB RAM.
    If RAM is constrained, set TRANSFORMERS_CACHE and pre-download at build time.

  Phase 1 total:  0 MB GPU,  ~1 GB RAM (with HuggingFace model)
  Recommended instance: ECS Fargate 2 vCPU / 4 GB RAM
  If running without HuggingFace: 2 vCPU / 2 GB RAM is fine.


=============================================================
 PHASE 2 — GPU REQUIRED FOR FACE + VOICE MODELS
=============================================================

Models below load onto GPU at startup and stay resident.
Numbers are VRAM usage at inference time (batch size = 1).
Each number includes the model weights + activation buffers.

  Model              Framework     GPU VRAM (inference)   Notes
  ──────────────────────────────────────────────────────────────────────────
  rppg_detector      ONNX/PyTorch  ~800 MB                MediaPipe on CPU,
                                                          signal processing on GPU
  gan_detector       PyTorch CNN   ~1,200 MB              ResNet-50 backbone
                                                          fine-tuned for forensics
  skin_physics       PyTorch       ~600 MB                Optical flow + landmark
                                                          tracking per frame batch
  jitter_analyzer    CPU+GPU       ~200 MB                Mostly signal processing,
                                                          small GPU footprint
  clone_detector     ONNX          ~400 MB                Lightweight voice encoder

  Phase 2 subtotal:  ~3,200 MB VRAM (models resident)
  Peak inference:    +~800 MB activation buffers during face analysis
  Phase 2 total:     ~4,000 MB VRAM peak

  Plus Phase 1 HuggingFace on CPU: no VRAM impact (stays in RAM).


=============================================================
 INSTANCE RECOMMENDATION
=============================================================

  Phase    Workload         Recommended         VRAM     Notes
  ────────────────────────────────────────────────────────────────────────
  1        CPU only         Fargate 2vCPU/4GB   0        No GPU needed at all
  2        Face+voice       g4dn.xlarge         16 GB    Comfortable headroom
  2        High throughput  g4dn.2xlarge        32 GB    2x T4, run 2 workers
  2 alt    Budget option    g4dn.xlarge         16 GB    16GB T4, ~4GB used, fine

  VERDICT FOR DEVOPS: g4dn.xlarge is the right call for Phase 2.
  VRAM budget: ~4 GB used out of 16 GB available = 12 GB headroom.
  This gives room for:
    - Multiple concurrent inference requests
    - Future model upgrades without re-provisioning
    - Phase 3 additions (review fraud, financial models) if they go GPU

  Do NOT use g4dn.medium (8 GB VRAM) — tight margin, no headroom.
  Do NOT use p3 instances — V100 is overkill for inference, expensive.


=============================================================
 DOCKER-COMPOSE (LOCAL DEV WITH GPU)
=============================================================

For developers with an NVIDIA GPU (optional — Phase 1 works without):

  ml_engine:
    build: ./ml_engine
    ports:
      - "8001:8001"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - CUDA_VISIBLE_DEVICES=0

Phase 1 developers without GPU: remove the `deploy.resources` block entirely.
Service will start in CPU mode automatically.


=============================================================
 PHASE 2 DOCKERFILE CHANGE (ML ENGINEER WILL HANDLE)
=============================================================

Switch base image when starting Phase 2:

  # Phase 1 (current)
  FROM python:3.11-slim

  # Phase 2 (uncomment when needed)
  # FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

  # Also uncomment in requirements.txt:
  # mediapipe==0.10.9
  # opencv-python==4.9.0.80
  # librosa==0.10.1

ML Engineer will open a PR for this change at Phase 2 kickoff.
DevOps: no action needed until that PR is merged.


=============================================================
 KUBERNETES RESOURCE LIMITS
=============================================================

Phase 1 (current):
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "4"
      memory: "8Gi"

Phase 2 (add GPU node pool):
  resources:
    requests:
      cpu: "4"
      memory: "8Gi"
      nvidia.com/gpu: "1"
    limits:
      cpu: "8"
      memory: "16Gi"
      nvidia.com/gpu: "1"
  nodeSelector:
    node.kubernetes.io/instance-type: g4dn.xlarge


=============================================================
 STARTUP BEHAVIOUR FOR DEVOPS HEALTH PROBES
=============================================================

  Phase 1 startup time: ~30 seconds
    - HuggingFace model load from disk: ~20s
    - Smoke tests: ~5s
    - FastAPI bind: ~2s

  Phase 2 startup time: ~90 seconds
    - CUDA context init: ~15s
    - Neural model loads: ~45s
    - Smoke tests (GPU inference): ~20s
    - FastAPI bind: ~2s

  Kubernetes probe config for Phase 2:
    livenessProbe:
      initialDelaySeconds: 120    # was 45 in Phase 1
      periodSeconds: 30
      timeoutSeconds: 10
    readinessProbe:
      initialDelaySeconds: 120
      periodSeconds: 10

  /health response time: < 50ms always (no inference in health check).
  phase2_ready field will be false until Phase 2 models are loaded.
  Do not route face/voice requests to pods where phase2_ready=false.
