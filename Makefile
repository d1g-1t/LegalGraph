SHELL = pwsh.exe
.SHELLFLAGS = -NoProfile -NonInteractive -Command
COMPOSE = docker compose
API = legalops-api

.PHONY: setup up down build test test-unit test-cov lint format migrate migrate-down seed seed-kb models logs logs-worker shell clean demo health

setup: build up migrate models seed
	@Write-Host "Setup complete. Run 'make health' to verify."

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

test:
	$(COMPOSE) exec -T $(API) pytest tests/ -v --tb=short -q

test-unit:
	$(COMPOSE) exec -T $(API) pytest tests/unit/ -v

test-cov:
	$(COMPOSE) exec -T $(API) pytest tests/ --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/

format:
	ruff check --fix src/ tests/; ruff format src/ tests/

migrate:
	$(COMPOSE) run --rm migrations alembic upgrade head

migrate-down:
	$(COMPOSE) run --rm migrations alembic downgrade -1

seed:
	$(COMPOSE) exec -T $(API) python -m scripts.seed_demo_users

seed-kb:
	$(COMPOSE) exec -T $(API) python -m scripts.seed_knowledge_base

models:
	$(COMPOSE) exec -T ollama ollama pull llama3.1:8b
	$(COMPOSE) exec -T ollama ollama pull nomic-embed-text

logs:
	$(COMPOSE) logs -f $(API)

logs-worker:
	$(COMPOSE) logs -f celery-worker

shell:
	$(COMPOSE) exec $(API) bash

clean:
	$(COMPOSE) down -v --remove-orphans

demo:
	$(COMPOSE) exec -T $(API) python -m scripts.demo_pipeline

health:
	@Write-Host "Checking API health..."
	@Invoke-RestMethod -Uri http://localhost:8079/api/v1/health/live -Method Get | ConvertTo-Json
