# HumanEye — Local Demo
**Cost: $0 | Requirements: Docker Desktop (free)**

---

## Start in 60 seconds

```bash
# 1. Clone / unzip the demo folder
cd humaneye-demo

# 2. Start everything
docker-compose up

# 3. Open the dashboard
open dashboard/demo.html
# OR just double-click dashboard/demo.html in your file explorer

# API docs auto-open at:
# http://localhost:8000/docs
```

That's it. No accounts, no API keys, no cloud, no credit card.

---

## What the demo shows

### Dashboard (`dashboard/demo.html`)
Open this file directly in your browser. Shows:
- Verification metrics (total, today, avg score, AI detected)
- Live verification panel — paste any text, get a Human Trust Score in real time
- Recent verifications table with scores, verdicts, and flags
- Keystroke biometrics captured while you type

### Try these scenarios with the client:

**Scenario 1 — Real human cover letter**
Click "Load human sample" → Verify now
Result: Score 80+, verdict "Human", no flags

**Scenario 2 — AI-generated cover letter**
Click "Load AI sample" → Verify now
Result: Score 20–40, verdict "Blocked", flag: "AI vocabulary pattern detected"

**Scenario 3 — Live API call** (while docker-compose is running)
Open http://localhost:8000/docs in browser
Try `POST /api/v1/verify` with the example payload
See the raw JSON response

---

## Architecture (all local, zero cloud)

```
Your laptop
├── PostgreSQL (port 5432)  ← stores verifications
├── Redis (port 6379)       ← rate limiting
├── Backend API (port 8000) ← FastAPI, all endpoints
├── ML Engine (port 8001)   ← scoring logic
└── dashboard/demo.html     ← open directly, no server needed
```

---

## What's real vs demo-mode

| Feature | Demo | Production |
|---|---|---|
| API endpoints | Real FastAPI | Same |
| Scoring logic | Heuristic (fast) | PyTorch models |
| Database | Real PostgreSQL | Same schema |
| Auth | Accepts any `he_demo_` key | bcrypt verified |
| Behavioral capture | Real keystrokes captured | Same SDK |
| Rate limiting | Real Redis sliding window | Same |

The scoring in demo mode uses vocabulary analysis and timing statistics — no GPU, no ML library. You can see it working on real input.

---

## Pitch talking points from the demo

**Show the live panel:**
"Watch — I'll paste an AI-generated cover letter. [paste] Score: 23. Blocked. Now a real one written by a person. [paste] Score: 87. Human. Same endpoint. This is what HR teams need right now."

**Show the API docs:**
"Any platform integrates this in one `POST` call. Same way they'd add Stripe. Three lines of code."

**Show the table:**
"Every verification logged, auditable, with the specific signals that triggered the flag. The HR team can see exactly why an application was flagged."

---

## Stopping

```bash
docker-compose down
```

Data persists in Docker volumes. Run `docker-compose down -v` to wipe everything.

---

## Files

```
humaneye-demo/
├── docker-compose.yml      ← start everything
├── db/
│   └── init.sql            ← schema + demo data
├── backend/
│   ├── main.py             ← FastAPI app (all endpoints)
│   ├── requirements.txt
│   └── Dockerfile.dev
├── ml_engine/
│   ├── api/main.py         ← scoring engine
│   ├── requirements.txt
│   └── Dockerfile.dev
└── dashboard/
    └── demo.html           ← open directly in browser
```
