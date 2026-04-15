from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.core.telemetry import setup_telemetry
from src.presentation.api.v1 import api_v1_router
from src.presentation.exception_handlers import register_exception_handlers
from src.presentation.middleware import PrometheusMiddleware, RequestIDMiddleware, SecureHeadersMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup / shutdown hooks."""
    settings = get_settings()
    setup_logging()
    setup_telemetry()

    logger.info(
        "legalops_startup",
        environment=settings.app_env,
        debug=settings.debug,
        api_port=settings.api_port,
    )

    try:
        from src.infrastructure.database import build_engine

        engine = build_engine(settings.database_url)
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
        logger.info("database_ready", url=settings.database_url.split("@")[-1])
    except Exception as exc:
        logger.error("database_startup_fail", error=str(exc))

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        logger.info("redis_ready")
    except Exception as exc:
        logger.warning("redis_startup_fail", error=str(exc))

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            logger.info("ollama_ready", models=models)
    except Exception as exc:
        logger.warning("ollama_startup_fail", error=str(exc))

    yield

    logger.info("legalops_shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="LegalOpsAI-Pipeline",
        description=(
            "Enterprise-grade multi-agent AI system for automating legal operations "
            "of Russian legal entities."
        ),
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)

    app.include_router(api_v1_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=settings.debug,
    )
