<#
.SYNOPSIS
    LegalOpsAI-Pipeline — Windows task runner (Makefile replacement)

.DESCRIPTION
    Usage: .\run.ps1 <target>

    Targets:
      setup        Full build from clone (build + up + migrate + models + seed)
      up           Start all containers
      down         Stop all containers
      build        Rebuild Docker images
      test         Run all tests inside API container
      test-unit    Run unit tests only
      test-cov     Run tests with coverage HTML report
      lint         ruff check + mypy
      format       Auto-format with ruff
      migrate      alembic upgrade head
      migrate-down alembic downgrade -1
      seed         Seed demo users + knowledge base
      models       Pull Ollama LLM models
      logs         Tail API container logs
      logs-worker  Tail Celery worker logs
      shell        Open bash shell in API container
      clean        Stop containers and remove all volumes
      demo         Run demo pipeline script
#>

param([string]$Target = "help")

$ErrorActionPreference = "Stop"
$API_CONTAINER = "legalops-api"
$WORKER_CONTAINER = "legalops-celery-worker"

function Invoke-Setup {
    Write-Host "🚀 LegalOpsAI-Pipeline — Full Setup" -ForegroundColor Green
    Write-Host "──────────────────────────────────────"

    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "[+] .env created from .env.example" -ForegroundColor Cyan
    }

    Write-Host "`n[1/6] Building Docker images..." -ForegroundColor Cyan
    docker compose build

    Write-Host "`n[2/6] Starting all services..." -ForegroundColor Cyan
    docker compose up -d

    Write-Host "`n[3/6] Waiting 15s for PostgreSQL to be ready..."
    Start-Sleep 15

    Write-Host "`n[4/6] Running database migrations..." -ForegroundColor Cyan
    docker compose run --rm migrations alembic upgrade head

    Write-Host "`n[5/6] Pulling Ollama models (this may take several minutes)..." -ForegroundColor Cyan
    try { docker compose exec -T ollama ollama pull llama3.1:8b } catch { Write-Warning "llama3.1:8b pull failed (non-fatal)" }
    try { docker compose exec -T ollama ollama pull nomic-embed-text } catch { Write-Warning "nomic-embed-text pull failed (non-fatal)" }

    Write-Host "`n[6/6] Seeding demo users..." -ForegroundColor Cyan
    try { docker compose exec -T $API_CONTAINER python -m scripts.seed_demo_users } catch { Write-Warning "Seed failed (non-fatal)" }

    Write-Host ""
    Write-Host "✅ Setup complete!" -ForegroundColor Green
    Write-Host "   API:      http://localhost:8079/docs"
    Write-Host "   Grafana:  http://localhost:3001  (admin / legalops2024)"
    Write-Host "   Flower:   http://localhost:5556"
    Write-Host "   Langfuse: http://localhost:3002"
}

switch ($Target) {
    "setup" { Invoke-Setup }

    "up" {
        docker compose up -d
        Write-Host "✅ All services started" -ForegroundColor Green
    }

    "down" {
        docker compose down
        Write-Host "🛑 All services stopped" -ForegroundColor Yellow
    }

    "restart" { docker compose restart }

    "build" { docker compose build }

    "test" {
        docker compose exec -T $API_CONTAINER pytest tests/ -v --tb=short -q
    }

    "test-unit" {
        docker compose exec -T $API_CONTAINER pytest tests/unit/ -v
    }

    "test-cov" {
        docker compose exec -T $API_CONTAINER pytest tests/ --cov=src --cov-report=html --cov-report=term
    }

    "lint" {
        ruff check src/ tests/
        ruff format --check src/ tests/
        mypy src/
    }

    "format" {
        ruff check --fix src/ tests/
        ruff format src/ tests/
    }

    "migrate" {
        docker compose run --rm migrations alembic upgrade head
    }

    "migrate-down" {
        docker compose run --rm migrations alembic downgrade -1
    }

    "seed" {
        docker compose exec -T $API_CONTAINER python -m scripts.seed_demo_users
        docker compose exec -T $API_CONTAINER python -m scripts.seed_knowledge_base
    }

    "models" {
        docker compose exec -T ollama ollama pull llama3.1:8b
        docker compose exec -T ollama ollama pull nomic-embed-text
    }

    "logs" { docker compose logs -f $API_CONTAINER }

    "logs-worker" { docker compose logs -f $WORKER_CONTAINER }

    "logs-all" { docker compose logs -f }

    "shell" { docker compose exec $API_CONTAINER bash }

    "clean" {
        docker compose down -v --remove-orphans
        Write-Host "🧹 All volumes removed" -ForegroundColor Yellow
    }

    "demo" {
        docker compose exec -T $API_CONTAINER python -m scripts.demo_pipeline
    }

    "help" {
        Get-Help $MyInvocation.MyCommand.Path -Detailed
    }

    default {
        Write-Error "Unknown target: '$Target'. Run '.\run.ps1 help' for usage."
    }
}
