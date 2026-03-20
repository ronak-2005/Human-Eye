# HumanEye ML Engine — Cross-Team API Contracts
# What every other role must deliver to ML, and what ML delivers back.
# Version 1.0 | ML Engineer owns this document.

=============================================================
 SECTION 1: WHAT ML EXPOSES (Internal API on port 8001)
=============================================================

The backend calls ML via HTTP. ML never talks to the frontend directly.
ML never touches the database. ML never calls external services.

─── Endpoint 1: POST /analyze ───────────────────────────────
Called by: backend/services/ml_client.py

Request (JSON):
{
  "session_id": "uuid-string",
  "signals": {
    "keystrokes": [
      {"key": "KeyA", "keydown_time": 0.0, "keyup_time": 85.2}
      // key = key CODE (e.g. "KeyA", "Space", "Backspace")
      // NEVER the character value ("a"). Privacy requirement.
      // timestamps in milliseconds, relative to session start
    ],
    "mouse_events": [
      {"x": 400.5, "y": 300.1, "timestamp": 120.5, "event_type": "move"},
      {"x": 450.0, "y": 320.0, "timestamp": 2400.0, "event_type": "click", "button": 0}
      // event_type: "move" | "click" | "enter" | "leave"
    ],
    "scroll_events": [
      {"scroll_y": 0.0, "timestamp": 0.0, "direction": "down", "velocity": 5.2}
    ],
    "text_content": "Cover letter or resume text here..."
    // null if not applicable for this action_type
  },
  "context": {
    "action_type": "job_application",
    // "job_application" | "review" | "exam" | "login" | "generic"
    "platform_user_id": "customer-platform-user-id",
    "ip_address": "1.2.3.4",
    "user_agent": "Mozilla/5.0...",
    "session_duration_ms": 45000
  }
}

Response (JSON):
{
  "behavioral_score": 0.82,        // 0-1, null if no behavioral signals
  "text_score": 0.71,              // 0-1, null if no text signals
  "combined_score": 0.78,          // 0-1 weighted fusion
  "human_trust_score": 78,         // 0-100 final score (this is what the backend uses)
  "flags": ["resume_high_buzzword_density"],
  "signal_scores": {               // Per-detector breakdown
    "keystroke": 0.85,
    "mouse": 0.79,
    "resume": 0.71,
    "vocabulary": 0.68
  },
  "confidence": "medium",          // "high" | "medium" | "low"
  "processing_time_ms": 142.5
}

─── Endpoint 2: POST /analyze/face (Phase 2) ────────────────
Request:
{
  "session_id": "uuid",
  "video_frames": ["base64...", "base64..."],  // JPEG frames
  "frame_rate": 30.0,
  "context": { ... }
}

Response:
{
  "liveness_score": 0.91,
  "deepfake_probability": 0.08,
  "skin_physics_pass": true,
  "rppg_bpm": 72.5,
  "asymmetry_score": 0.23,
  "flags": []
}

─── Endpoint 3: POST /analyze/voice (Phase 2) ───────────────
Request:
{
  "session_id": "uuid",
  "audio_data": "base64-encoded-WAV",
  "sample_rate": 16000,
  "context": { ... }
}

Response:
{
  "clone_probability": 0.04,
  "jitter_score": 0.52,
  "shimmer_score": 1.8,
  "breathing_natural": true,
  "flags": []
}

─── Endpoint 4: GET /health ─────────────────────────────────
Response:
{
  "status": "ok",
  "models_loaded": ["keystroke", "mouse", "scroll", "resume", "vocab", "fusion"],
  "gpu_available": false,
  "phase1_ready": true,
  "phase2_ready": false
}

─── Endpoint 5: GET /models ─────────────────────────────────
Response:
{
  "loaded_models": {
    "keystroke": {"version": "1.0.0", "last_trained": "2024-01", "accuracy": null},
    ...
  }
}


=============================================================
 SECTION 2: WHAT ML NEEDS FROM BACKEND ENGINEER
=============================================================

1. SIGNAL PAYLOAD CONTRACT
   The backend must forward signals EXACTLY as received from the browser SDK.
   DO NOT transform or flatten the signal arrays before sending to ML.
   ML expects the raw event arrays as documented above.

2. ACTION_TYPE FIELD (CRITICAL)
   This field changes which detectors are weighted most heavily.
   Backend must map the customer's use case to one of:
     "job_application" → heavy text analysis weight
     "review"          → heavy text analysis weight
     "exam"            → heavy keystroke + text weight
     "login"           → heavy keystroke weight only
     "generic"         → equal weights

   If the customer hasn't specified, use "generic".

3. TIMESTAMP FORMAT
   All timestamps must be in milliseconds (float), relative to session start.
   The SDK sends absolute timestamps — backend must normalize to relative
   before forwarding to ML.
   Formula: signal.timestamp = abs_timestamp - session_start_timestamp

4. TEXT CONTENT LIMITS
   Truncate text_content to 50,000 characters before sending.
   ML will not process text over this limit (returns 422).

5. SIGNAL MINIMUM SIZES
   ML will return score=0.5 + flag if below minimum:
   - keystrokes: need >= 20 events for keystroke model
   - mouse_events: need >= 30 events for mouse model
   - scroll_events: need >= 15 events for scroll model
   - text_content: need >= 50 words for text models
   Backend should warn customers if sessions are too short.

6. INTERNAL NETWORK ONLY
   ML engine is on internal network, port 8001.
   Backend calls: http://ml-engine:8001/analyze
   This URL must be in backend/.env as ML_ENGINE_URL.

7. TIMEOUT HANDLING
   ML processing target: < 300ms for full pipeline.
   Backend must set HTTP timeout to 5000ms (allow for cold start).
   On ML timeout: return score=null, verdict="unavailable" to customer.
   Do NOT retry immediately — use exponential backoff.

8. MLFLOW TRACKING SERVER
   ML needs access to: http://mlflow:5000
   Backend does not interact with MLflow. DevOps sets it up.
   ML_TRACKING_URI env var must be set in ml_engine container.


=============================================================
 SECTION 3: WHAT ML NEEDS FROM FRONTEND / SDK ENGINEER
=============================================================

The browser SDK is ML's data source. Signal quality from the SDK directly
determines detection accuracy. This is the most important interface.

1. KEYSTROKE EVENTS — EXACT FORMAT REQUIRED
   {
     "key": "KeyA",          // ALWAYS key CODE, never character value
     "keydown_time": 1234567890.123,  // performance.now() timestamp (ms)
     "keyup_time":   1234567890.234
   }

   NEVER send: {"key": "a", ...}  // character value is a privacy violation
   ALWAYS send: {"key": "KeyA", ...}  // key code only

   Key code reference: https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code
   Special keys to capture: Backspace, Delete, Space, Enter, Tab
   Keys to EXCLUDE from capture (privacy): CapsLock state, modifier keys

2. MOUSE EVENTS — EXACT FORMAT REQUIRED
   Move events:  {"x": 400.5, "y": 300.1, "timestamp": ms, "event_type": "move"}
   Click events: {"x": 400.5, "y": 300.1, "timestamp": ms, "event_type": "click", "button": 0}

   Sampling rate: MAX 50Hz (one event per 20ms). DO NOT send every mousemove.
   Batching: accumulate for 500ms, send one batch. Not one event per request.
   Coordinates: always relative to viewport (0,0 = top-left).

3. SCROLL EVENTS — EXACT FORMAT REQUIRED
   {
     "scroll_y": 1200.5,          // window.scrollY at event time
     "timestamp": 1234567890.123, // performance.now()
     "direction": "down",         // "up" | "down"
     "velocity": 8.5              // pixels per ms
   }

4. SESSION METADATA (send once at session start)
   {
     "session_id": "uuid-v4",         // Unique per verification attempt
     "session_start_time": 1234567890.123,  // performance.now() at init
     "viewport_width": 1920,
     "viewport_height": 1080,
     "device_pixel_ratio": 2.0,
     "has_touch": false,
     "connection_type": "wifi"         // from navigator.connection if available
   }

5. SIGNAL QUALITY TARGETS
   For reliable detection, the SDK should aim to capture:
   - Keystroke: >= 50 events per form submission (encourage longer text fields)
   - Mouse: >= 100 move events + >= 2 click events per session
   - Scroll: >= 20 events per session
   If these minimums aren't met, ML will flag "insufficient_data" but still score.

6. TIMESTAMP NORMALIZATION
   Send raw performance.now() timestamps.
   ML's signal_cleaner.py normalizes them to relative timestamps.
   DO NOT normalize in the SDK — ML handles this.

7. VIDEO/AUDIO CAPTURE (Phase 2)
   For face detection: capture frames as JPEG base64, 30fps, minimum 90 frames (3 seconds).
   For voice detection: capture as WAV, 16kHz mono, minimum 3 seconds.
   Prompt user to slowly turn their head left-right (for skin physics test).
   NEVER store video/audio on disk or in any database — ML processes in memory only.


=============================================================
 SECTION 4: WHAT ML NEEDS FROM DEVOPS ENGINEER
=============================================================

1. ENVIRONMENT VARIABLES (ml_engine container)
   ML_ENGINE_PORT=8001
   ML_ENGINE_WORKERS=2          # Scale up in Phase 2 with GPU
   ML_TRACKING_URI=http://mlflow:5000
   TRANSFORMERS_CACHE=/app/.cache/huggingface
   MODEL_DIR=/app/ml_engine/saved_models
   LOG_LEVEL=INFO
   ENVIRONMENT=production       # "development" | "staging" | "production"

2. MLFLOW SERVER
   ML needs a running MLflow tracking server.
   docker-compose service: mlflow on port 5000
   Persistent storage: mlflow_data volume for experiment history
   S3 artifact store for production (DevOps sets up S3 bucket + IAM role)

3. GPU NODE (Phase 2)
   For face/voice models: ECS Fargate with g4dn.xlarge (NVIDIA T4)
   In docker-compose.yml for local dev, GPU passthrough for developers who have it.
   Phase 1 is CPU-only — no GPU needed.

4. SAVED MODELS DIRECTORY
   /app/ml_engine/saved_models/ must be a persistent volume.
   In production: mount an EBS volume or S3-synced directory.
   On container restart: models must still be there (not wiped).

5. HEALTH CHECK CONFIG
   Kubernetes liveness probe: GET /health, timeout 10s, period 30s
   Kubernetes readiness probe: GET /health, check phase1_ready=true
   If phase1_ready=false, do not send traffic to this pod.

6. PORT EXPOSURE
   Port 8001: INTERNAL ONLY. Never expose to internet.
   Security group / network policy: only backend service can reach port 8001.
   ML must not be reachable from outside the VPC.

7. RESOURCE LIMITS (Phase 1, CPU-only)
   CPU: 2 vCPU request, 4 vCPU limit
   Memory: 4GB request, 8GB limit (HuggingFace models are memory-hungry)

8. STARTUP TIME
   ML engine takes ~30s to start (model loading).
   Set initialDelaySeconds=45 on liveness probe to avoid premature restarts.

9. LOGGING
   ML logs to stdout (structured JSON).
   DevOps ships logs to CloudWatch.
   ML never logs raw signal values — only metadata (session_id, score ranges, flags).


=============================================================
 SECTION 5: WHAT ML NEEDS FROM SECURITY ENGINEER
=============================================================

1. MODEL FILE INTEGRITY
   Security will define the SHA256 signing process for saved models.
   ML will implement: verify hash before loading any .pt or .onnx file.
   Any model with unverified hash must NOT be loaded — fail with error.

2. ADVERSARIAL TESTING SCHEDULE
   Security will coordinate monthly adversarial example tests.
   ML needs: sample adversarial inputs (e.g. bots that mimic human timing).
   ML will: retrain or adjust thresholds when adversarial accuracy drops below 80%.

3. DATA RETENTION ENFORCEMENT
   Raw behavioral signals: deleted after 90 days (ML must implement deletion job).
   Security will audit this quarterly.
   ML delivers: automated script ml_engine/scripts/cleanup_old_signals.py

4. INFERENCE LOGGING POLICY (NON-NEGOTIABLE)
   ML may ONLY log:
     - session_id
     - score range (e.g. "score: 0.7-0.8", not exact value)
     - flags triggered
     - processing_time_ms
     - model versions used
   ML must NEVER log:
     - actual signal arrays (keystrokes, mouse coordinates)
     - text_content
     - ip_address or user_agent (these stay in backend logs only)

5. NO EXTERNAL CALLS
   ML engine must make zero external HTTP calls during inference.
   HuggingFace models are downloaded at build time (in Dockerfile).
   ML must not call any third-party API at runtime.
   Security will verify this with network policy enforcement.
