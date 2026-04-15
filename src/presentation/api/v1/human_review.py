from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.dto import HumanReviewOut, PaginatedResponse, ReviewDecisionIn
from src.application.use_cases import ReviewDecisionUseCase
from src.domain.entities import ApiUser
from src.domain.value_objects import ReviewStatus
from src.infrastructure.database.repositories import HumanReviewRepository, PipelineRunRepository
from src.presentation.deps import get_current_user, get_db_session, require_roles

router = APIRouter()


def _review_to_dto(t) -> HumanReviewOut:
    return HumanReviewOut(
        id=t.id,
        pipeline_run_id=t.pipeline_run_id,
        assigned_reviewer_id=t.assigned_reviewer_id,
        priority=t.priority,
        reason=t.reason,
        status=t.status,
        deadline_at=t.deadline_at,
        decision=t.decision,
        comment=t.comment,
        edited_response=t.edited_response,
        created_at=t.created_at,
        decided_at=t.decided_at,
    )


@router.get("/pending", response_model=PaginatedResponse, summary="Pending review tasks")
async def list_pending_reviews(
    user: ApiUser = Depends(require_roles("ADMIN", "REVIEWER", "LAWYER")),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session=Depends(get_db_session),
) -> PaginatedResponse:
    repo = HumanReviewRepository(session)
    tasks = await repo.list_pending(limit=limit, offset=offset)
    return PaginatedResponse(
        items=[_review_to_dto(t).model_dump() for t in tasks],
        total=len(tasks),
        limit=limit,
        offset=offset,
    )


@router.get("/{pipeline_run_id}", response_model=HumanReviewOut, summary="Get review task by pipeline")
async def get_review_task(
    pipeline_run_id: UUID,
    user: ApiUser = Depends(require_roles("ADMIN", "REVIEWER", "LAWYER")),
    session=Depends(get_db_session),
) -> HumanReviewOut:
    repo = HumanReviewRepository(session)
    task = await repo.get_by_pipeline(pipeline_run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    return _review_to_dto(task)


@router.post("/{pipeline_run_id}/decision", response_model=HumanReviewOut, summary="Submit review decision")
async def submit_decision(
    pipeline_run_id: UUID,
    body: ReviewDecisionIn,
    user: ApiUser = Depends(require_roles("ADMIN", "REVIEWER", "LAWYER")),
    session=Depends(get_db_session),
) -> HumanReviewOut:
    review_repo = HumanReviewRepository(session)
    pipeline_repo = PipelineRunRepository(session)
    use_case = ReviewDecisionUseCase(
        review_repo=review_repo,
        pipeline_repo=pipeline_repo,
    )
    await use_case.execute(
        pipeline_run_id=pipeline_run_id,
        dto=body,
        reviewer_id=user.id,
    )
    task = await review_repo.get_by_pipeline(pipeline_run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    return _review_to_dto(task)


@router.get("/sla-alerts", summary="Review tasks at SLA risk")
async def sla_alerts(
    user: ApiUser = Depends(require_roles("ADMIN", "REVIEWER")),
    session=Depends(get_db_session),
) -> list[dict]:
    repo = HumanReviewRepository(session)
    tasks = await repo.list_pending(limit=100, offset=0)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    alerts = []
    for t in tasks:
        if t.deadline_at and t.status == ReviewStatus.PENDING:
            remaining = (t.deadline_at - now).total_seconds()
            if remaining < 3600:
                alerts.append({
                    "task_id": str(t.id),
                    "pipeline_run_id": str(t.pipeline_run_id),
                    "sla_deadline": t.deadline_at.isoformat(),
                    "remaining_seconds": max(0, int(remaining)),
                    "overdue": remaining <= 0,
                    "priority": t.priority,
                })
    return sorted(alerts, key=lambda x: x["remaining_seconds"])
