# HumanEye — Backend API Contract
Version 1.0 | Share this with every team member

```
Base URL (local):      http://localhost:8000
Base URL (staging):    https://staging-api.humaneye.io
Base URL (production): https://api.humaneye.io
Auth header:           Authorization: Bearer he_<your_api_key>
Swagger docs:          GET /docs  (always up to date)
```

## Error format (all endpoints, always)
```json
{ "error": "snake_case_type", "message": "Human readable", "code": "SCREAMING_SNAKE" }
```

---

## POST /api/v1/verify — CORE ENDPOINT

```json
REQUEST:
{
  "session_id": "uuid",
  "signals": {
    "keystrokes":    [{ "key": "KeyA", "keydown_time": 120.5, "keyup_time": 220.1 }],
    "mouse_events":  [{ "x": 400, "y": 300, "event_type": "move", "timestamp": 120.5 }],
    "scroll_events": [{ "scroll_y": 0, "direction": "down", "velocity": 5.2, "timestamp": 0 }],
    "text_content":  "Resume or cover letter text...",
    "video_frame_data": null,
    "audio_data": null
  },
  "context": {
    "action_type":         "job_application",
    "platform_user_id":    "your-user-id",
    "ip_address":          "1.2.3.4",
    "user_agent":          "Mozilla/5.0...",
    "session_duration_ms": 45000
  }
}

RESPONSE 200:
{
  "verification_id":    "uuid",
  "human_trust_score":  87,
  "verdict":            "human",
  "confidence":         "high",
  "flags":              [],
  "processing_time_ms": 142,
  "signals_analyzed":   ["keystroke", "mouse", "text"],
  "liveness_score":       null,
  "deepfake_probability": null,
  "clone_probability":    null
}
```

**Score ranges:**
| Score | Verdict | Action |
|-------|---------|--------|
| 80–100 | human | Permit |
| 65–79 | likely_human | Permit + monitor |
| 50–64 | uncertain | Challenge |
| 25–49 | suspicious | Elevated challenge |
| 0–24 | synthetic | Block |
| null | unavailable | Do not block — flag for review |

**action_type options:** `job_application` · `review` · `exam` · `login` · `generic`

**All timestamps** must be relative to session start in ms. SDK sends absolute `performance.now()` — backend normalizes automatically.

**Phase 2:** Pass `video_frame_data` (list of base64 JPEGs, min 90 frames) for face liveness. Pass `audio_data` (base64 WAV 16kHz mono, min 3s) for voice clone detection.

---

## POST /api/v1/signals
Stream raw events from SDK before calling /verify.
```json
{ "session_id": "uuid", "event_type": "keystroke", "events": [...], "timestamp": "ISO8601" }
```
Response: `{ "accepted": 42, "session_id": "uuid" }`

---

## GET /api/v1/scores/{platform_user_id}
Persistent trust score compounding over time.
```json
{ "platform_user_id": "user-123", "current_score": 84.5, "verification_count": 7,
  "last_verified_at": "2024-01-01T12:00:00", "verdict": "human" }
```

## GET /api/v1/verifications?page=1&page_size=20
## GET /api/v1/verifications/{id}

---

## POST /api/v1/webhooks/register
```json
REQUEST:  { "url": "https://yourapp.com/webhook", "secret": "hmac-secret" }
RESPONSE: { "id": "uuid", "url": "...", "is_active": true, "created_at": "..." }
```
**Webhook payload** (POSTed to your URL on each verification):
```json
{ "event": "verification.complete", "verification_id": "uuid",
  "human_trust_score": 87, "verdict": "human", "confidence": "high",
  "flags": [], "platform_user_id": "user-123", "timestamp": "ISO8601" }
```
**Signature:** `X-HumanEye-Signature: sha256=<hmac_hex>` · `X-HumanEye-Verification-Id: <uuid>`
Verify: `hmac.new(secret, body, sha256).hexdigest()`
**Idempotent:** Deduplicate on `verification_id` — Celery may deliver more than once on retry.

---

## POST /api/v1/keys  →  create key (returns plaintext ONCE)
## GET  /api/v1/keys  →  list keys
## DELETE /api/v1/keys/{id}  →  revoke key
## GET /api/v1/health  →  system health (DevOps / k8s probe)

---

## WHAT I NEED FROM EACH ROLE

### ML Engineer → expose on ml_engine:8001 (internal only)

```
POST /analyze       → { human_trust_score, combined_score, behavioral_score,
                        text_score, flags, signal_scores, confidence, processing_time_ms }
POST /analyze/face  → { liveness_score, deepfake_probability, skin_physics_pass,
                        rppg_bpm, asymmetry_score, flags, phase }
POST /analyze/voice → { clone_probability, jitter_score, shimmer_score,
                        breathing_natural, flags, phase }
GET  /health        → { status, phase1_ready, phase2_ready, models_loaded }
GET  /models        → { loaded_models, versions, last_trained }
```
- All scores must be **float 0.0–1.0** (backend multiplies by 100 for `human_trust_score`)  
  OR return `human_trust_score` as **int 0–100** directly (preferred)
- Communicate schema changes ≥ 1 week in advance

### Frontend (Next.js Dashboard)
- CORS allowed: `http://localhost:3000` (dev), update `.env` `ALLOWED_ORIGINS` for prod
- Same Bearer auth as customers
- Calls: `GET /verifications`, `GET /verifications/{id}`, `GET /scores/{id}`,  
  `GET /keys`, `POST /keys`, `DELETE /keys/{id}`
- Swagger docs always live at `/docs`

### DevOps
- Dockerfile: `backend/Dockerfile` ✅
- All env vars: `.env.example` ✅
- Health endpoint: `GET /api/v1/health` — returns `ml_engine.phase1_ready` ✅
- Prometheus metrics: `GET /metrics` ✅
- Migrations: `alembic upgrade head` (run as one-off ECS task before deploy) ✅
- Migration files: `backend/alembic/versions/` ✅
- New env vars: always added to `.env.example` before PR

### Security Engineer
Already implemented per spec:
- ✅ `Depends(get_authenticated_customer)` on every protected route
- ✅ Tenant isolation: every query filters `WHERE user_id = customer_id`
- ✅ Cross-tenant: always 404, never 403
- ✅ `make_request_log()` for every inbound log line
- ✅ Middleware order: PayloadSize → RequestId → SecurityHeaders → CORS → Timing
- ✅ `validate_webhook_url()` before storing any webhook
- ✅ bcrypt API keys, plaintext shown once, log fingerprint only
- ✅ Signal data never logged
- Security-audited endpoints: `POST /verify` · `POST /keys` · `GET /verifications/{id}` · `GET /scores/{id}` · `DELETE /keys/{id}`
