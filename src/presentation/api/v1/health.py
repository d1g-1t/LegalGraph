from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from src.application.dto import HealthOut
from src.presentation.deps import get_db_session

router = APIRouter()


@router.get("/live", summary="Liveness probe")
async def liveness() -> dict:
    return {"status": "alive"}


@router.get("/ready", response_model=HealthOut, summary="Readiness probe")
async def readiness(session=Depends(get_db_session)) -> HealthOut:
    db_status = "unknown"
    redis_status = "unknown"
    ollama_status = "unknown"

    try:
        from sqlalchemy import text

        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "fail"

    try:
        import redis.asyncio as aioredis

        from src.core.config import get_settings

        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        redis_status = "ok"
    except Exception:
        redis_status = "fail"

    try:
        import httpx

        from src.core.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_status = "ok" if resp.status_code == 200 else "fail"
    except Exception:
        ollama_status = "fail"

    overall = all(s == "ok" for s in [db_status, redis_status, ollama_status])
    return HealthOut(
        status="ready" if overall else "degraded",
        database=db_status,
        redis=redis_status,
        ollama=ollama_status,
    )


@router.get("/models", summary="Available LLM models")
async def list_models() -> dict:
    try:
        import httpx

        from src.core.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [
                {"name": m["name"], "size": m.get("size"), "modified_at": m.get("modified_at")}
                for m in data.get("models", [])
            ]
            return {"models": models, "count": len(models)}
    except Exception as exc:
        return {"models": [], "count": 0, "error": str(exc)}


@router.get("/metrics", summary="Prometheus metrics endpoint")
async def prometheus_metrics() -> Response:
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain",
        )
