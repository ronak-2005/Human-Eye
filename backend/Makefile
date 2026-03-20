# HumanEye — Make commands
# Usage: make <target>

.PHONY: up down migrate migrate-new test-backend logs-backend db-shell redis-cli health format lint

## ── Local dev ────────────────────────────────────────────────────────────────
up:
	docker-compose up --build

up-backend:
	docker-compose up backend postgres timescaledb redis celery celery_beat --build

down:
	docker-compose down -v

## ── Database ─────────────────────────────────────────────────────────────────
migrate:
	docker-compose exec backend alembic upgrade head

migrate-new:
	docker-compose exec backend alembic revision --autogenerate -m "$(m)"

db-shell:
	docker-compose exec postgres psql -U humaneye -d humaneye

ts-shell:
	docker-compose exec timescaledb psql -U humaneye -d humaneye_signals

## ── Testing ──────────────────────────────────────────────────────────────────
test-backend:
	docker-compose exec backend pytest tests/ -v --cov=. --cov-report=term-missing

test-local:
	cd backend && pytest tests/ -v

## ── Linting / formatting ─────────────────────────────────────────────────────
lint:
	docker-compose exec backend black . --check
	docker-compose exec backend ruff check .

format:
	docker-compose exec backend black .
	docker-compose exec backend ruff check . --fix

## ── Logs ─────────────────────────────────────────────────────────────────────
logs-backend:
	docker-compose logs -f backend

logs-all:
	docker-compose logs -f

## ── Shells ───────────────────────────────────────────────────────────────────
redis-cli:
	docker-compose exec redis redis-cli

backend-shell:
	docker-compose exec backend bash

## ── Health check ─────────────────────────────────────────────────────────────
health:
	@echo "=== Backend ===" && curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
	@echo "=== ML Engine ===" && curl -s http://localhost:8001/health | python3 -m json.tool

## ── Secrets (DevOps use) ─────────────────────────────────────────────────────
secret-set:
	docker-compose exec vault vault kv put secret/$(key) value=$(value)
