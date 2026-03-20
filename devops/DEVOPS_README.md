# HumanEye — DevOps Infrastructure

## Quick Start (local dev)

```bash
cp .env.example .env          # fill in values
make up                       # starts all 12 services
make migrate                  # apply DB migrations
```

**Services you get:**

| Service | Port | What it is |
|---|---|---|
| Backend (FastAPI) | 8000 | Main API — `http://localhost:8000/docs` |
| ML Engine | 8001 | Detection API (internal) |
| Dashboard (Next.js) | 3000 | Customer portal |
| PostgreSQL | 5432 | Primary database |
| TimescaleDB | 5433 | Behavioral signals |
| Redis | 6379 | Cache + rate limiting |
| MLflow | 5000 | Model tracking |
| Grafana | 3001 | Metrics dashboard (admin/admin) |
| Vault | 8200 | Secrets (token: `dev-root-token`) |

---

## Repo structure (DevOps-owned files)

```
humaneye/
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf              ← AWS provider + remote state
│   │   ├── variables.tf         ← all config variables
│   │   ├── vpc.tf               ← networking + security groups
│   │   ├── ecs.tf               ← Fargate services + ECR + autoscaling
│   │   ├── rds.tf               ← PostgreSQL 15 + read replica
│   │   └── alb_s3_outputs.tf    ← ALB, S3, CloudWatch alarms, outputs
│   ├── docker/
│   │   ├── backend.Dockerfile   ← FastAPI (dev hot-reload + prod gunicorn)
│   │   ├── ml_engine.Dockerfile ← PyTorch CPU→GPU switch in Phase 2
│   │   ├── dashboard.Dockerfile ← Next.js multi-stage build
│   │   ├── redis.conf           ← Redis configuration
│   │   ├── prometheus.yml       ← Metrics scrape config
│   │   └── init-scripts/
│   │       ├── postgres-init.sql     ← DB setup + extensions
│   │       └── timescale-init.sql    ← Hypertables + retention policy
│   └── k8s/                    ← Phase 2: EKS manifests (TBD)
├── .github/
│   └── workflows/
│       └── ci-cd.yml            ← Full CI/CD pipeline
├── docker-compose.yml           ← Local dev environment
├── Makefile                     ← All common commands
└── .env.example                 ← ALL required environment variables
```

---

## What I need from each role

### From Backend Engineer

These are **blockers** — I cannot finish the Docker/ECS setup without them:

| What I need | Why | When |
|---|---|---|
| `backend/requirements.txt` | To build the Docker image | Week 1 |
| `backend/requirements-test.txt` | For CI test stage | Week 1 |
| Working `Dockerfile` (or confirm mine works) | Production image | Week 1 |
| `.env.example` additions for any new variables | My `.env.example` is the source of truth | Ongoing |
| `GET /api/v1/health` endpoint | ALB health checks + CI smoke tests | Week 1 |
| `GET /metrics` endpoint (Prometheus format) | Grafana dashboards | Week 2 |
| Alembic migration files in `backend/alembic/` | CI runs `alembic upgrade head` before deploy | Before first deploy |
| Webhook delivery confirmed idempotent | So I can retry failed webhook celery tasks safely | Week 3 |

**Variables I provide to you (paste into your config):**
```
DATABASE_URL        ← from `terraform output rds_endpoint`
TIMESCALE_URL       ← separate TimescaleDB endpoint
REDIS_URL           ← from `terraform output redis_endpoint`
ML_ENGINE_URL       ← service discovery DNS: http://ml-engine.humaneye.local:8001
```

---

### From ML Engineer

| What I need | Why | When |
|---|---|---|
| `ml_engine/requirements.txt` | Docker image build | Week 1 |
| Working `GET /health` on port 8001 | Service discovery health check | Week 1 |
| `GET /metrics` (Prometheus) on port 8001 | Grafana monitoring | Week 2 |
| List of all env vars the ML engine needs | I add them to ECS task definition | Week 1 |
| Model file naming convention for S3 | I set up versioned S3 bucket for you | Week 2 |
| MLflow experiment names you'll use | I configure MLflow server and storage | Week 2 |
| GPU memory requirement per model (Phase 2) | I choose correct g4dn instance size | Month 9 |

**Variables I provide to you:**
```
S3_BUCKET           ← from `terraform output s3_models_bucket`
MLFLOW_TRACKING_URI ← http://mlflow.humaneye.local:5000 (prod)
TIMESCALE_URL       ← same as backend
REDIS_URL           ← redis://... (db index 1, separate from backend)
```

**Model deployment SOP (our shared process):**
1. You push trained model to MLflow staging
2. You tag it `production-candidate`
3. I run `make deploy-model MODEL=<run-id>` which copies to S3 production prefix
4. I trigger ECS service redeploy
5. We both watch Grafana for inference latency spike

---

### From Frontend Engineer

| What I need | Why | When |
|---|---|---|
| `dashboard/package.json` with all scripts (`dev`, `build`, `lint`, `type-check`) | CI pipeline depends on these script names | Week 1 |
| Confirm Next.js `output: 'standalone'` in `next.config.js` | My Dockerfile copies `.next/standalone` | Week 1 |
| No hardcoded `localhost` URLs — only `NEXT_PUBLIC_API_URL` | Works in staging/prod | Week 1 |
| List of any additional `NEXT_PUBLIC_*` env vars you need | I add them to ECS task definition | Ongoing |

**Variables I provide to you:**
```
NEXT_PUBLIC_API_URL     ← https://api.humaneye.io (prod) / https://staging-api.humaneye.io
NEXT_PUBLIC_WS_URL      ← wss://api.humaneye.io / wss://staging-api.humaneye.io
```

---

### From Security Engineer

| What I need | Why | When |
|---|---|---|
| List of required Vault secret paths | I bootstrap Vault with correct KV paths | Week 1 |
| Pen test schedule (quarterly from Month 6) | I open firewall rules temporarily | Month 6 |
| SOC 2 control list you need me to implement | I configure CloudTrail, VPC flow logs, etc. | Month 1 |
| Approval for IAM role policy documents | Security reviews before I apply to AWS | Week 2 |
| Required CloudTrail event categories | Audit log setup | Week 2 |

**What I provide to you:**
- All IAM role policies for review before applying
- CloudTrail logs in S3 (90-day retention)
- VPC Flow Logs enabled
- RDS encryption at rest (KMS)
- ElastiCache encryption in transit + at rest
- No production DB access without multi-party approval (enforced via IAM)
- Vault AppRole auth for services (no static tokens in production)

---

## External APIs — what I need keys for

These go into AWS Secrets Manager. You give me the key, I store it securely and inject it into the ECS task via `secrets:` in task definition. **Never put keys in `.env.example` values or git.**

| API | Who gets it | Where to get |
|---|---|---|
| iProov (liveness) | Backend + ML | https://portal.iproov.com |
| Plaid (open banking) | Backend | https://dashboard.plaid.com |
| Stripe (billing) | Backend | https://dashboard.stripe.com |
| MaxMind GeoIP2 | Backend | https://www.maxmind.com |
| Sendgrid (email) | Backend | https://app.sendgrid.com |
| Pinecone (vector DB) | ML Engine | https://app.pinecone.io |
| Polygon/Alchemy RPC | Backend (Phase 3) | https://www.alchemy.com |
| AWS credentials | DevOps only | IAM console |

---

## CI/CD Pipeline stages

```
PR opened / push to branch
    ↓
1. Lint         (Black, isort, ESLint, TypeScript)    ~2 min
    ↓
2. Test         (pytest backend + ml_engine, jest)     ~5 min  ← needs postgres + redis service
    ↓
3. Security     (Bandit Python, npm audit)             ~2 min
    ↓                         [only on push, not PRs]
4. Build        (Docker → ECR, SHA-tagged)             ~8 min
    ↓                         [develop branch only]
5. Deploy → Staging           (auto, no approval)      ~3 min
    ↓
6. Smoke test   (hit /health endpoints)
    ↓                         [main branch, after staging passes]
7. Deploy → Production        (MANUAL APPROVAL required in GitHub)
```

To approve production deploy: GitHub → Actions → workflow run → Review deployments → Approve.

---

## Monitoring alerts + runbooks

All alerts go to SNS → (add your email/Slack webhook to `aws_sns_topic.alerts`).

| Alert | Threshold | Runbook |
|---|---|---|
| P95 API latency | > 500ms for 2 min | Check ECS CPU, DB slow queries, ML engine latency |
| 5xx error rate | > 10 errors/min | Check ECS logs: `make logs-backend` or CloudWatch |
| Redis memory | > 80% | Check key TTLs, consider instance upgrade |
| ML inference time | > 300ms avg | Check model load, consider scaling ECS tasks |
| ECS task crash loop | 3 failed starts | Check CloudWatch logs for crash reason |
| RDS CPU | > 80% for 5 min | Check slow query log, consider read replica |

---

## Environments

| Env | Branch | Deploy | Data |
|---|---|---|---|
| `development` | any | `docker-compose up` | local only |
| `staging` | `develop` | automatic on merge | seeded test data |
| `production` | `main` | manual approval | real customers |

---

## Phase 2 infra changes (months 9–18)

When ML engineer needs GPU for face/voice detection:

1. Uncomment GPU base image in `ml_engine.Dockerfile`
2. Add `gpu_node_pool` to `ecs.tf` (g4dn.xlarge instances)
3. Deploy Neo4j (social graph analysis)
4. Deploy Pinecone index for behavioral fingerprinting
5. Migrate from ECS to EKS for HPA + rolling deploys

---

## Phase 3 infra changes (months 19–36)

1. ZK proof node infrastructure (Circom/SnarkJS compute tasks)
2. Polygon RPC connection + event listeners
3. Multi-region active-active for 99.99% enterprise SLA
4. SOC 2 Type II audit evidence collection
