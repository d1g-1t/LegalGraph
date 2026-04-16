"""API v1 — router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from src.presentation.api.v1 import (
    auth,
    escalations,
    health,
    human_review,
    knowledge,
    pipelines,
    requests,
)

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(requests.router, prefix="/requests", tags=["Requests"])
api_v1_router.include_router(pipelines.router, prefix="/pipelines", tags=["Pipelines"])
api_v1_router.include_router(human_review.router, prefix="/human-review", tags=["Human Review"])
api_v1_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge"])
api_v1_router.include_router(escalations.router, prefix="/escalations", tags=["Escalations"])
api_v1_router.include_router(health.router, prefix="/health", tags=["Health"])
