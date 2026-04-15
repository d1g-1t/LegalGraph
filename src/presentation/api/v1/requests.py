from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from src.application.dto import (
    PaginatedResponse,
    RequestOut,
    SubmitRequestIn,
    SubmitRequestOut,
)
from src.application.use_cases import SubmitRequestUseCase
from src.domain.entities import ApiUser
from src.infrastructure.database.repositories import (
    LegalRequestRepository,
    PipelineRunRepository,
)
from src.infrastructure.queue.tasks import run_pipeline_task
from src.presentation.deps import get_current_user, get_db_session, require_roles

router = APIRouter()


@router.post("/", response_model=SubmitRequestOut, status_code=201, summary="Submit legal request")
async def submit_request(
    body: SubmitRequestIn,
    user: ApiUser = Depends(require_roles("ADMIN", "LAWYER", "REVIEWER", "ANALYST", "VIEWER")),
    session=Depends(get_db_session),
) -> SubmitRequestOut:
    use_case = SubmitRequestUseCase(
        request_repo=LegalRequestRepository(session),
        pipeline_repo=PipelineRunRepository(session),
    )
    request_id, pipeline_run_id = await use_case.execute(
        body, requester_id=user.id, legal_entity_id=user.legal_entity_id or user.id,
    )
    run_pipeline_task.apply_async(args=[str(pipeline_run_id)], queue="legalops.pipeline")
    return SubmitRequestOut(request_id=request_id, pipeline_run_id=pipeline_run_id)


@router.get("/{request_id}/stream", summary="SSE stream of pipeline progress")
async def stream_pipeline_progress(
    request_id: UUID,
    user: ApiUser = Depends(get_current_user),
) -> EventSourceResponse:
    async def _event_generator():
        from src.infrastructure.database import build_session_factory
        from src.infrastructure.database.repositories import (
            AgentStepRepository,
            PipelineRunRepository,
        )

        session_factory = build_session_factory()
        seen_steps: set[str] = set()
        last_status = ""

        yield {"event": "request_created", "data": json.dumps({"request_id": str(request_id)})}

        for _ in range(300):
            try:
                async with session_factory() as session:
                    pipeline_repo = PipelineRunRepository(session)
                    step_repo = AgentStepRepository(session)

                    runs = await session.execute(
                        __import__("sqlalchemy", fromlist=["select"]).select(
                            __import__(
                                "src.infrastructure.database.models", fromlist=["PipelineRunModel"]
                            ).PipelineRunModel
                        ).where(
                            __import__(
                                "src.infrastructure.database.models", fromlist=["PipelineRunModel"]
                            ).PipelineRunModel.request_id == request_id
                        ).order_by(
                            __import__(
                                "src.infrastructure.database.models", fromlist=["PipelineRunModel"]
                            ).PipelineRunModel.started_at.desc()
                        ).limit(1)
                    )
                    run_model = runs.scalar_one_or_none()
                    if not run_model:
                        await asyncio.sleep(1)
                        continue

                    run_id = run_model.id
                    current_status = run_model.pipeline_status

                    steps = await step_repo.list_by_pipeline(run_id)
                    for step in steps:
                        step_key = f"{step.node_name}:{step.step_order}"
                        if step_key not in seen_steps:
                            seen_steps.add(step_key)
                            yield {
                                "event": "node_completed",
                                "data": json.dumps({
                                    "node_name": step.node_name,
                                    "step_order": step.step_order,
                                    "status": step.status,
                                    "duration_ms": step.duration_ms,
                                }),
                            }

                    if current_status != last_status:
                        last_status = current_status
                        if current_status == "AWAITING_REVIEW":
                            yield {
                                "event": "human_review_required",
                                "data": json.dumps({"pipeline_run_id": str(run_id)}),
                            }
                        elif current_status == "ESCALATED":
                            yield {
                                "event": "escalation_created",
                                "data": json.dumps({
                                    "pipeline_run_id": str(run_id),
                                    "escalation_case_id": str(run_model.escalation_case_id) if run_model.escalation_case_id else None,
                                }),
                            }
                        elif current_status == "COMPLETED":
                            yield {
                                "event": "completed",
                                "data": json.dumps({
                                    "pipeline_run_id": str(run_id),
                                    "category": run_model.category,
                                    "total_duration_ms": run_model.total_duration_ms,
                                }),
                            }
                            return
                        elif current_status == "FAILED":
                            yield {
                                "event": "failed",
                                "data": json.dumps({
                                    "pipeline_run_id": str(run_id),
                                    "error": run_model.error_message,
                                }),
                            }
                            return

            except Exception:
                pass

            await asyncio.sleep(1)

        yield {"event": "timeout", "data": json.dumps({"message": "Stream timeout after 5 minutes"})}

    return EventSourceResponse(_event_generator())


@router.get("/{request_id}", response_model=RequestOut, summary="Get request by ID")
async def get_request(
    request_id: UUID,
    user: ApiUser = Depends(get_current_user),
    session=Depends(get_db_session),
) -> RequestOut:
    repo = LegalRequestRepository(session)
    req = await repo.get_by_id(request_id)
    if not req:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Request not found")
    return RequestOut(
        id=req.id, requester_id=req.requester_id, legal_entity_id=req.legal_entity_id,
        channel=req.channel, priority=req.priority, raw_input=req.raw_input,
        submitted_at=req.submitted_at, status=req.status,
    )


@router.get("/", response_model=PaginatedResponse, summary="List requests")
async def list_requests(
    user: ApiUser = Depends(get_current_user),
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session=Depends(get_db_session),
) -> PaginatedResponse:
    repo = LegalRequestRepository(session)
    items = await repo.list_requests(
        legal_entity_id=user.legal_entity_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=[
            RequestOut(
                id=r.id, requester_id=r.requester_id, legal_entity_id=r.legal_entity_id,
                channel=r.channel, priority=r.priority, raw_input=r.raw_input,
                submitted_at=r.submitted_at, status=r.status,
            ).model_dump()
            for r in items
        ],
        total=len(items),
        limit=limit,
        offset=offset,
    )
