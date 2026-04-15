from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.dto import (
    AgentStepOut,
    AnalyticsOut,
    PaginatedResponse,
    PipelineRunOut,
)
from src.application.use_cases import AnalyticsUseCase
from src.domain.entities import ApiUser
from src.domain.value_objects import PipelineStatus
from src.infrastructure.database.repositories import (
    AgentStepRepository,
    HumanReviewRepository,
    KnowledgeChunkRepository,
    PipelineRunRepository,
)
from src.presentation.deps import get_current_user, get_db_session, require_roles

router = APIRouter()


def _run_to_dto(run) -> PipelineRunOut:
    return PipelineRunOut(
        id=run.id,
        request_id=run.request_id,
        thread_id=run.thread_id,
        pipeline_status=run.pipeline_status,
        category=run.category,
        risk_level=run.risk_level,
        classifier_confidence=float(run.classifier_confidence) if run.classifier_confidence is not None else None,
        generated_response=run.generated_response,
        final_response=run.final_response,
        verification_passed=run.verification_passed,
        legal_accuracy_score=float(run.legal_accuracy_score) if run.legal_accuracy_score is not None else None,
        hallucination_detected=run.hallucination_detected,
        requires_human_review=run.requires_human_review,
        human_decision=run.human_decision,
        trace_id=run.trace_id,
        node_timings=run.node_timings or {},
        total_duration_ms=run.total_duration_ms,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/{pipeline_id}", response_model=PipelineRunOut, summary="Get pipeline run")
async def get_pipeline_run(
    pipeline_id: UUID,
    user: ApiUser = Depends(get_current_user),
    session=Depends(get_db_session),
) -> PipelineRunOut:
    repo = PipelineRunRepository(session)
    run = await repo.get_by_id(pipeline_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return _run_to_dto(run)


@router.get("/{pipeline_id}/steps", response_model=list[AgentStepOut], summary="Get pipeline steps")
async def get_pipeline_steps(
    pipeline_id: UUID,
    user: ApiUser = Depends(get_current_user),
    session=Depends(get_db_session),
) -> list[AgentStepOut]:
    repo = AgentStepRepository(session)
    steps = await repo.list_by_pipeline(pipeline_id)
    return [
        AgentStepOut(
            id=s.id,
            node_name=s.node_name,
            step_order=s.step_order,
            status=s.status,
            model_name=s.model_name,
            prompt_tokens=s.prompt_tokens,
            completion_tokens=s.completion_tokens,
            duration_ms=s.duration_ms,
            error_message=s.error_message,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in steps
    ]


@router.get("/{pipeline_id}/trace", summary="Get pipeline trace for observability")
async def get_pipeline_trace(
    pipeline_id: UUID,
    user: ApiUser = Depends(get_current_user),
    session=Depends(get_db_session),
) -> dict:
    repo = PipelineRunRepository(session)
    run = await repo.get_by_id(pipeline_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    step_repo = AgentStepRepository(session)
    steps = await step_repo.list_by_pipeline(pipeline_id)

    return {
        "pipeline_id": str(pipeline_id),
        "pipeline_status": run.pipeline_status,
        "trace_id": run.trace_id,
        "category": run.category,
        "risk_level": run.risk_level,
        "total_duration_ms": run.total_duration_ms,
        "node_timings": run.node_timings,
        "steps": [
            {
                "node": s.node_name,
                "step_order": s.step_order,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "prompt_tokens": s.prompt_tokens,
                "completion_tokens": s.completion_tokens,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error": s.error_message,
            }
            for s in steps
        ],
    }


@router.post("/{pipeline_id}/retry", response_model=PipelineRunOut, summary="Retry failed pipeline")
async def retry_pipeline(
    pipeline_id: UUID,
    user: ApiUser = Depends(require_roles("ADMIN", "LAWYER")),
    session=Depends(get_db_session),
) -> PipelineRunOut:
    repo = PipelineRunRepository(session)
    run = await repo.get_by_id(pipeline_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.pipeline_status != PipelineStatus.FAILED:
        raise HTTPException(status_code=409, detail="Only failed pipelines can be retried")

    from src.domain.entities import PipelineRun
    from src.infrastructure.queue.tasks import run_pipeline_task

    new_run = PipelineRun(request_id=run.request_id, thread_id=str(run.request_id) + "-retry")
    await repo.create(new_run)
    run_pipeline_task.apply_async(args=[str(new_run.id)], queue="legalops.pipeline")
    return _run_to_dto(new_run)


@router.get("/analytics/summary", response_model=AnalyticsOut, summary="Analytics summary")
async def analytics_summary(
    user: ApiUser = Depends(require_roles("ADMIN", "ANALYST")),
    session=Depends(get_db_session),
) -> AnalyticsOut:
    use_case = AnalyticsUseCase(
        pipeline_repo=PipelineRunRepository(session),
        review_repo=HumanReviewRepository(session),
        chunk_repo=KnowledgeChunkRepository(session),
    )
    return await use_case.execute()
