# HumanEye — Data Flow Diagram
**Owner: Security Engineer | Version 1.0 | Update on every architecture change**

This document traces every piece of sensitive data through the system.
It answers: where does data enter, where does it go, where does it rest, when is it deleted?

---

## Flow 1: Behavioral Signal Capture → Verification Result

This is the primary data flow — the core product in action.

```
STEP 1: Customer's User Interacts with Form
════════════════════════════════════════════
User types on customer platform (e.g., job application form)

Browser SDK captures:
  ┌──────────────────────────────────────────────────┐
  │  Keystroke events:                               │
  │    { code: "KeyH", down: 1234.56, up: 1234.89 } │  ← Physical key + timing ONLY
  │    { code: "KeyE", down: 1235.12, up: 1235.31 } │  ← NO key values ever
  │                                                  │
  │  Mouse events:                                   │
  │    { x: 342, y: 198, t: 1234.90, type: "move" } │
  │                                                  │
  │  Scroll events:                                  │
  │    { pos: 450, t: 1235.50, vel: 12.3 }           │
  └──────────────────────────────────────────────────┘
  
  Buffered in Web Worker (never touches main thread)
  Batch-sent every 500ms to:

STEP 2: Signal Transmission (SDK → Backend API)
════════════════════════════════════════════════
POST https://api.humaneye.io/api/v1/signals
Headers: Authorization: Bearer he_live_[key]
Encryption: TLS 1.3 (Cloudflare → ALB)

Payload:
  {
    session_id: "uuid",
    signals: { keystrokes: [...], mouse_events: [...], scroll_events: [...] },
    context: { action_type: "job_application", platform_user_id: "...", ip: "..." }
  }

STEP 3: Backend API Receives Signal
═════════════════════════════════════
  1. Auth check: bcrypt verify API key
  2. Rate limit check: Redis counter
  3. Input validation: Pydantic schema
  4. Write raw signals to TimescaleDB (encrypted EBS)
     Table: behavioral_signals
     Retention: 90 days → automated deletion
  5. Queue ML analysis job: Celery → Redis

STEP 4: ML Engine Processes Signals
══════════════════════════════════════
  Internal call: POST ml-engine:8001/analyze
  Headers: X-Internal-Token: [vault-secret]

  ML Engine:
    ├── Loads verified model (hash checked)
    ├── Processes signals IN MEMORY
    │   ├── Keystroke dynamics model → behavioral_score (0–1)
    │   ├── Mouse dynamics model → mouse_score (0–1)
    │   └── Text model (if text_content provided) → text_score (0–1)
    ├── Fusion engine → combined_score (0–100)
    ├── Raw signal arrays DISCARDED from memory
    └── Returns to Backend:
        { behavioral_score, text_score, combined_score, flags }

  IMPORTANT: Raw arrays never leave the ML engine.
  ML engine only returns aggregated scores.

STEP 5: Backend Stores Result + Returns to Customer
════════════════════════════════════════════════════
  Backend:
    ├── Stores in PostgreSQL (encrypted RDS):
    │   Table: verifications
    │   Columns: id, customer_id, session_id, score, verdict, flags, timestamp
    │   NOT stored: raw signal arrays (already deleted after ML processing)
    │
    ├── Updates trust score in PostgreSQL:
    │   Table: trust_scores
    │
    └── Returns to customer platform:
        {
          verification_id: "uuid",
          score: 87,
          verdict: "human",
          confidence: "high",
          flags: [],
          processing_time_ms: 142
        }

STEP 6: Signal Aging and Deletion
═══════════════════════════════════
  Celery beat job runs daily:
    DELETE FROM behavioral_signals WHERE captured_at < NOW() - INTERVAL '90 days'
  
  After 90 days: only the verification RESULT (score + verdict) remains.
  The raw timing data that produced it is gone.
```

---

## Flow 2: Text Content (Resume / Cover Letter)

Text follows a different path — it is more sensitive (contains personal information).

```
Customer SDK:
  eye.verify({ text_content: coverLetterText })
  
  Text transmitted in HTTPS payload to Backend API

Backend API:
  Passes text_content field to ML Engine in analysis request
  Does NOT store text_content in database

ML Engine:
  Analyzes text IN MEMORY:
    ├── Vocabulary frequency analysis
    ├── Human imperfection index
    └── Specificity scoring
  
  Returns only: { text_score: 0.73, text_flags: ["high_synonym_variety"] }
  
  text_content string is discarded after analysis
  Never written to any storage

Result: Text is analyzed but never persisted.
```

---

## Flow 3: Dashboard — Customer Viewing Their Data

```
Customer Engineer:
  Opens https://app.humaneye.io
  
Browser:
  GET /api/v1/verifications
  Cookie: session=[httpOnly token]
  
Backend API:
  Validates session cookie
  Queries PostgreSQL:
    SELECT * FROM verifications WHERE customer_id = [session.customer_id]
    (never queries another customer's data)
  
  Returns verification list (scores, verdicts, timestamps)
  
  Note: Raw signal data never returned in dashboard — it's already deleted or aggregated
```

---

## Flow 4: Liveness Check — Video/Audio (Phase 2)

This is the highest-sensitivity flow. Video and audio are **never stored**.

```
Browser:
  Captures video frames from camera (with user consent)
  Captures audio from microphone (with user consent)
  
  Sends frames/audio over TLS to Backend API

Backend API:
  Immediately forwards to ML Engine (does NOT buffer to database)
  
ML Engine:
  Receives video frames / audio in memory
  Runs:
    ├── rPPG blood flow analysis (video)
    ├── Skin physics verification (video)
    ├── Voice jitter/shimmer analysis (audio)
  
  Frames and audio IMMEDIATELY discarded after analysis
  Never written to disk, never written to any database
  
  Returns: { liveness_score, deepfake_probability, voice_clone_probability }

Backend API:
  Stores only the result scores in verifications table
  The source video/audio is gone — it was never stored

GDPR note: "Never stored" is architecturally enforced, not just policy.
```

---

## Flow 5: ZK Credential Issuance (Phase 3)

```
User completes full verification (score > 80 over multiple sessions)

Backend:
  Generates ZK proof input:
    { user_is_verified_human: true }
  
  Sends to ZK proof service (Circom + SnarkJS)
  
ZK Proof Service:
  Generates proof that:
    "This user passed HumanEye verification"
    WITHOUT revealing WHO the user is
  
  Proof anchored on Polygon blockchain (public, verifiable)
  
  Credential issued as W3C Verifiable Credential:
    {
      type: "HumanCredential",
      proof: [zk-proof],
      issuer: "did:humaneye:...",
      // No name, no email, no behavioral data — just the proof
    }

User holds credential in their wallet.
Third-party platforms verify without contacting HumanEye.
HumanEye cannot track which platforms user presents credential to.
```

---

## Data Location Summary

| Data | Created | Stored | Deleted | Never Stored |
|---|---|---|---|---|
| Keystroke timing | Browser SDK | TimescaleDB | 90 days | Key values |
| Mouse timing | Browser SDK | TimescaleDB | 90 days | Exact coordinates beyond 90 days |
| Text content | Browser SDK | Never | N/A | ✅ |
| Video frames | Browser SDK | Never | N/A | ✅ |
| Audio | Browser SDK | Never | N/A | ✅ |
| Verification scores | Backend | PostgreSQL | 2 years | |
| API keys (plaintext) | Key generation | Never | N/A | ✅ |
| API keys (hashed) | Key generation | PostgreSQL | Until revoked | |
| Session tokens | Login | Redis (hashed) | 24h TTL | Plaintext |
| Secrets/passwords | Vault | Vault only | On rotation | Env vars, code |
| Audit logs | CloudTrail/Vault | S3 immutable | 1 year min | |

---

## Encryption in Transit — All Flows

| Segment | Protocol | Notes |
|---|---|---|
| Browser → Cloudflare | TLS 1.3 | Certificate pinning in SDK |
| Cloudflare → ALB | TLS 1.3 | AWS-managed certificate |
| ALB → Backend | HTTP | Internal VPC only, no internet exposure |
| Backend → ML Engine | HTTP | Internal VPC only, port 8001 |
| Backend → PostgreSQL | TLS | pg_ssl=require |
| Backend → Redis | TLS | redis+ssl:// |
| Backend → Vault | TLS | Vault TLS certificate |
| Any service → S3 | HTTPS | via VPC endpoint |

---

*Any change to data flows must be reflected in this document before implementation.*
*New data flows touching personal data require GDPR assessment before building.*
