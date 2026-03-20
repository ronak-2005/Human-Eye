# HumanEye

Human Verification Infrastructure for the AI Age.

## Quick Start

```bash
# 1. Start backend stack
docker-compose up backend postgres timescaledb redis celery celery_beat --build

# 2. Run migrations (new terminal)
make migrate

# 3. Verify health
make health

# 4. Open interactive API docs
open http://localhost:8000/docs
```

## Services

| Service       | URL                          | Owner              |
|---------------|------------------------------|--------------------|
| Backend API   | http://localhost:8000        | Backend engineer   |
| API Docs      | http://localhost:8000/docs   | Backend engineer   |
| ML Engine     | http://localhost:8001        | ML engineer        |
| Dashboard     | http://localhost:3000        | Frontend engineer  |
| MLflow        | http://localhost:5000        | ML engineer        |
| Grafana       | http://localhost:3001        | DevOps             |
| Vault         | http://localhost:8200        | DevOps             |
| PostgreSQL    | localhost:5432               | DevOps             |
| TimescaleDB   | localhost:5433               | DevOps             |
| Redis         | localhost:6379               | DevOps             |

## Common Commands

```bash
make up              # start everything
make up-backend      # start backend stack only (no dashboard/ml)
make migrate         # run alembic migrations
make migrate-new m="add_table_name"  # create new migration
make test-backend    # run tests
make lint            # check formatting
make format          # auto-format
make logs-backend    # tail backend logs
make health          # curl health on all services
make db-shell        # psql into postgres
make redis-cli       # redis-cli
```

## Architecture

```
Customer SDK (browser/mobile)
        │
        ▼
POST /api/v1/verify   ← Backend (port 8000)
        │
        ├── PostgreSQL (port 5432)   ← verifications, users, api_keys, scores
        ├── TimescaleDB (port 5433)  ← raw signal streams (90-day retention)
        ├── Redis (port 6379)        ← rate limiting, celery broker
        ├── ML Engine (port 8001)    ← behavioral + text + face + voice
        └── Celery                   ← async webhook delivery
```

## Score Ranges

| Score  | Verdict       | Action                        |
|--------|---------------|-------------------------------|
| 80–100 | human         | Permit immediately            |
| 65–79  | likely_human  | Permit with monitoring        |
| 50–64  | uncertain     | Challenge required            |
| 25–49  | suspicious    | Elevated challenge + review   |
| 0–24   | synthetic     | Block + flag                  |
| null   | unavailable   | ML down — do not block, review|

## API Quick Reference

```bash
# Verify a user
curl -X POST http://localhost:8000/api/v1/verify \
  -H "Authorization: Bearer he_your_key" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"uuid","signals":{"keystrokes":[],"text_content":"cover letter..."},"context":{"action_type":"job_application","platform_user_id":"user-123"}}'

# Get persistent trust score
curl http://localhost:8000/api/v1/scores/user-123 \
  -H "Authorization: Bearer he_your_key"

# Health check
curl http://localhost:8000/api/v1/health
```

## Team Contracts

- **`backend/API_CONTRACT.md`** — full API spec for all teams
- **`backend/services/ml_client.py`** — ML engineer contract (what backend expects)
- **`backend/core/auth.py`** — Security engineer owned
- **`backend/core/middleware.py`** — Security engineer owned

## Phases

| Phase | Timeline  | Goal                                      |
|-------|-----------|-------------------------------------------|
| 1     | Months 1–8  | Behavioral biometrics + text analysis   |
| 2     | Months 9–18 | Face liveness + voice clone detection   |
| 3     | Months 19–36| ZK credentials + reputation ledger      |
| 4     | Years 4–5   | Global standard + government integrations|
