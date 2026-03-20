# ============================================================
# HumanEye — Makefile
# Common developer commands
# ============================================================

.PHONY: help up down logs shell-backend shell-ml test lint build deploy-staging

# Default target
help:
	@echo ""
	@echo "  HumanEye DevOps Commands"
	@echo ""
	@echo "  Local Dev:"
	@echo "    make up              — Start all services (docker-compose up)"
	@echo "    make down            — Stop all services"
	@echo "    make logs            — Tail all logs"
	@echo "    make logs-backend    — Tail backend logs only"
	@echo "    make logs-ml         — Tail ML engine logs only"
	@echo "    make restart-backend — Restart backend without full rebuild"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate         — Run Alembic migrations (dev)"
	@echo "    make migrate-new m=  — Create new migration: make migrate-new m=add_users"
	@echo "    make db-shell        — Open psql shell"
	@echo "    make timescale-shell — Open TimescaleDB shell"
	@echo ""
	@echo "  Testing:"
	@echo "    make test            — Run all tests"
	@echo "    make test-backend    — Backend tests only"
	@echo "    make test-ml         — ML engine tests only"
	@echo "    make test-coverage   — Tests with coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint            — Run all linters"
	@echo "    make format          — Auto-format all code"
	@echo ""
	@echo "  Build:"
	@echo "    make build           — Build all Docker images"
	@echo "    make build-backend   — Build backend image only"
	@echo "    make build-ml        — Build ML engine image only"
	@echo ""
	@echo "  Infrastructure:"
	@echo "    make tf-plan         — Terraform plan (staging)"
	@echo "    make tf-apply        — Terraform apply (staging)"
	@echo "    make secrets-list    — List Vault secrets"
	@echo ""

# ── Local Dev ─────────────────────────────────────────────
up:
	docker-compose up -d
	@echo "Services running:"
	@echo "  Backend:   http://localhost:8000"
	@echo "  Backend docs: http://localhost:8000/docs"
	@echo "  ML Engine: http://localhost:8001"
	@echo "  Dashboard: http://localhost:3000"
	@echo "  MLflow:    http://localhost:5000"
	@echo "  Grafana:   http://localhost:3001 (admin/admin)"
	@echo "  Vault:     http://localhost:8200 (token: dev-root-token)"

down:
	docker-compose down

down-volumes:
	docker-compose down -v
	@echo "WARNING: All local data volumes deleted"

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-ml:
	docker-compose logs -f ml_engine

logs-celery:
	docker-compose logs -f celery

restart-backend:
	docker-compose restart backend

shell-backend:
	docker-compose exec backend bash

shell-ml:
	docker-compose exec ml_engine bash

# ── Database ──────────────────────────────────────────────
migrate:
	docker-compose exec backend alembic upgrade head
	@echo "Migrations applied"

migrate-new:
	docker-compose exec backend alembic revision --autogenerate -m "$(m)"

migrate-down:
	docker-compose exec backend alembic downgrade -1

db-shell:
	docker-compose exec postgres psql -U humaneye -d humaneye

timescale-shell:
	docker-compose exec timescaledb psql -U humaneye -d humaneye_signals

redis-cli:
	docker-compose exec redis redis-cli

# ── Testing ───────────────────────────────────────────────
test:
	docker-compose exec backend pytest tests/ -v
	docker-compose exec ml_engine pytest tests/ -v

test-backend:
	docker-compose exec backend pytest tests/ -v -x

test-ml:
	docker-compose exec ml_engine pytest tests/ -v -x

test-coverage:
	docker-compose exec backend pytest tests/ --cov=. --cov-report=html -v
	@echo "Coverage report: backend/htmlcov/index.html"

# ── Code Quality ──────────────────────────────────────────
lint:
	docker-compose exec backend black --check .
	docker-compose exec backend isort --check-only .
	docker-compose exec backend flake8 .
	docker-compose exec backend bandit -r . -ll
	@echo "Dashboard lint:"
	cd dashboard && npm run lint

format:
	docker-compose exec backend black .
	docker-compose exec backend isort .
	@echo "Code formatted"

# ── Build ─────────────────────────────────────────────────
build:
	docker-compose build --parallel

build-backend:
	docker build -f infrastructure/docker/backend.Dockerfile --target production -t humaneye/backend:local .

build-ml:
	docker build -f infrastructure/docker/ml_engine.Dockerfile --target production -t humaneye/ml-engine:local .

build-dashboard:
	docker build -f infrastructure/docker/dashboard.Dockerfile --target production -t humaneye/dashboard:local .

# ── Terraform / Infra ─────────────────────────────────────
tf-init:
	cd infrastructure/terraform && terraform init

tf-plan:
	cd infrastructure/terraform && \
	terraform plan -var="environment=staging" -out=tfplan.staging

tf-apply:
	cd infrastructure/terraform && \
	terraform apply tfplan.staging

tf-destroy-staging:
	@echo "WARNING: This destroys staging infrastructure!"
	cd infrastructure/terraform && \
	terraform destroy -var="environment=staging"

# ── Vault (secrets) ───────────────────────────────────────
secrets-list:
	VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=dev-root-token \
	vault kv list secret/humaneye

secrets-get:
	VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=dev-root-token \
	vault kv get secret/humaneye/$(key)

# ── Health checks ─────────────────────────────────────────
health:
	@curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
	@echo ""
	@curl -s http://localhost:8001/health | python3 -m json.tool

health-staging:
	@curl -s https://staging-api.humaneye.io/api/v1/health | python3 -m json.tool
