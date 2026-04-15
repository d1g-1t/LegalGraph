from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.dto import (
    AssignLawyerIn,
    EscalationOut,
    PaginatedResponse,
    ResolveEscalationIn,
)
from src.domain.entities import ApiUser
from src.domain.value_objects import EscalationStatus
from src.infrastructure.database.repositories import EscalationRepository
from src.presentation.deps import get_current_user, get_db_session, require_roles

router = APIRouter()


def _case_to_dto(c) -> EscalationOut:
    return EscalationOut(
        id=c.id,
        pipeline_run_id=c.pipeline_run_id,
        category=c.category,
        risk_level=c.risk_level,
        priority=c.priority,
        reason=c.reason,
        assigned_lawyer_id=c.assigned_lawyer_id,
        status=c.status,
        resolution_note=c.resolution_note,
        sla_deadline=c.sla_deadline,
        created_at=c.created_at,
        resolved_at=c.resolved_at,
    )


@router.get("/", response_model=PaginatedResponse, summary="List escalations")
async def list_escalations(
    user: ApiUser = Depends(require_roles("ADMIN", "LAWYER")),
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session=Depends(get_db_session),
) -> PaginatedResponse:
    """List all escalation cases (newest first)."""
    repo = EscalationRepository(session)
    cases = await repo.list_cases(status=status, limit=limit, offset=offset)
    return PaginatedResponse(
        items=[_case_to_dto(c).model_dump() for c in cases],
        total=len(cases),
        limit=limit,
        offset=offset,
    )


@router.get("/{case_id}", response_model=EscalationOut, summary="Get escalation")
async def get_escalation(
    case_id: UUID,
    user: ApiUser = Depends(require_roles("ADMIN", "LAWYER")),
    session=Depends(get_db_session),
) -> EscalationOut:
    """Retrieve a specific escalation case."""
    repo = EscalationRepository(session)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return _case_to_dto(case)


@router.post("/{case_id}/assign", response_model=EscalationOut, summary="Assign lawyer to escalation")
async def assign_escalation(
    case_id: UUID,
    body: AssignLawyerIn,
    user: ApiUser = Depends(require_roles("ADMIN")),
    session=Depends(get_db_session),
) -> EscalationOut:
    """Assign an escalation case to a specific lawyer."""
    repo = EscalationRepository(session)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if case.status == EscalationStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Cannot assign resolved escalation")

    case.assigned_lawyer_id = body.lawyer_id
    case.status = EscalationStatus.ASSIGNED
    await repo.update(case)

    updated = await repo.get_by_id(case_id)
    return _case_to_dto(updated)


@router.post("/{case_id}/resolve", response_model=EscalationOut, summary="Resolve escalation")
async def resolve_escalation(
    case_id: UUID,
    body: ResolveEscalationIn,
    user: ApiUser = Depends(require_roles("ADMIN", "LAWYER")),
    session=Depends(get_db_session),
) -> EscalationOut:
    """Resolve an escalation case with notes."""
    repo = EscalationRepository(session)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if case.status == EscalationStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Already resolved")

    case.status = EscalationStatus.RESOLVED
    case.resolution_note = body.resolution_note
    case.resolved_at = datetime.now(timezone.utc)
    await repo.update(case)

    updated = await repo.get_by_id(case_id)
    return _case_to_dto(updated)
