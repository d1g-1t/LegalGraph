"""Application use cases — orchestrate domain services, repos and infra.

Business logic lives here; routers just call use cases.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from src.application.dto import (
    AnalyticsOut,
    ReviewDecisionIn,
    SubmitRequestIn,
)
from src.core.logging import get_logger
from src.domain.entities import (
    EscalationCase,
    HumanReviewTask,
    LegalRequest,
    PipelineRun,
)
from src.domain.repositories import (
    IEscalationRepository,
    IHumanReviewRepository,
    IKnowledgeChunkRepository,
    IKnowledgeDocumentRepository,
    ILegalRequestRepository,
    IPipelineRunRepository,
    IUserRepository,
)
from src.domain.services import RiskPolicyService
from src.domain.value_objects import PipelineStatus, ReviewStatus

logger = get_logger(__name__)


class SubmitRequestUseCase:
    """Accept a legal request, create pipeline run, enqueue processing."""

    def __init__(
        self,
        request_repo: ILegalRequestRepository,
        pipeline_repo: IPipelineRunRepository,
    ) -> None:
        self._request_repo = request_repo
        self._pipeline_repo = pipeline_repo

    async def execute(
        self,
        dto: SubmitRequestIn,
        requester_id: UUID,
        legal_entity_id: UUID,
    ) -> tuple[UUID, UUID]:
        """Create request + pipeline run. Returns (request_id, pipeline_run_id)."""
        request_id = uuid4()
        pipeline_run_id = uuid4()

        request = LegalRequest(
            id=request_id,
            requester_id=requester_id,
            legal_entity_id=legal_entity_id,
            channel=dto.channel,
            priority=dto.priority,
            raw_input=dto.raw_input,
            status="PROCESSING",
        )
        await self._request_repo.create(request)

        run = PipelineRun(
            id=pipeline_run_id,
            request_id=request_id,
            thread_id=str(pipeline_run_id),
            pipeline_status=PipelineStatus.PENDING,
        )
        await self._pipeline_repo.create(run)

        logger.info(
            "request_submitted",
            request_id=str(request_id),
            pipeline_run_id=str(pipeline_run_id),
        )
        return request_id, pipeline_run_id


class ReviewDecisionUseCase:
    """Process a human reviewer's decision and resume pipeline."""

    def __init__(
        self,
        review_repo: IHumanReviewRepository,
        pipeline_repo: IPipelineRunRepository,
    ) -> None:
        self._review_repo = review_repo
        self._pipeline_repo = pipeline_repo

    async def execute(
        self,
        pipeline_run_id: UUID,
        dto: ReviewDecisionIn,
        reviewer_id: UUID,
    ) -> None:
        """Record decision and update pipeline run."""
        task = await self._review_repo.get_by_pipeline(pipeline_run_id)
        if not task:
            raise ValueError(f"No review task for pipeline {pipeline_run_id}")

        task.decision = dto.decision
        task.comment = dto.comment
        task.edited_response = dto.edited_response
        task.status = ReviewStatus.DECIDED
        task.decided_at = datetime.now(UTC)
        await self._review_repo.update(task)

        run = await self._pipeline_repo.get_by_id(pipeline_run_id)
        if run:
            run.human_decision = dto.decision
            if dto.decision == "APPROVED":
                run.final_response = run.generated_response
                run.pipeline_status = PipelineStatus.COMPLETED
                run.completed_at = datetime.now(UTC)
            elif dto.decision == "EDITED":
                run.generated_response = dto.edited_response
                run.pipeline_status = PipelineStatus.RUNNING
            elif dto.decision == "REJECTED":
                run.pipeline_status = PipelineStatus.ESCALATED
            await self._pipeline_repo.update(run)

        logger.info(
            "review_decision_recorded",
            pipeline_run_id=str(pipeline_run_id),
            decision=dto.decision,
        )


class CreateEscalationUseCase:
    """Create an escalation case from pipeline context."""

    def __init__(
        self,
        escalation_repo: IEscalationRepository,
        pipeline_repo: IPipelineRunRepository,
    ) -> None:
        self._escalation_repo = escalation_repo
        self._pipeline_repo = pipeline_repo

    async def execute(
        self,
        pipeline_run_id: UUID,
        reason: str,
        context_package: dict,
    ) -> UUID:
        """Create escalation and update pipeline."""
        run = await self._pipeline_repo.get_by_id(pipeline_run_id)
        if not run:
            raise ValueError(f"Pipeline run not found: {pipeline_run_id}")

        case_id = uuid4()
        priority = RiskPolicyService.escalation_priority_from_risk(run.risk_level or "MEDIUM")
        case = EscalationCase(
            id=case_id,
            pipeline_run_id=pipeline_run_id,
            category=run.category or "OTHER",
            risk_level=run.risk_level or "MEDIUM",
            priority=priority,
            reason=reason,
            context_package=context_package,
            sla_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await self._escalation_repo.create(case)

        run.escalation_case_id = case_id
        run.pipeline_status = PipelineStatus.ESCALATED
        run.completed_at = datetime.now(UTC)
        await self._pipeline_repo.update(run)

        logger.info("escalation_created", case_id=str(case_id), pipeline_run_id=str(pipeline_run_id))
        return case_id


class AnalyticsUseCase:
    """Compute analytics aggregates."""

    def __init__(
        self,
        pipeline_repo: IPipelineRunRepository,
        review_repo: IHumanReviewRepository,
        chunk_repo: IKnowledgeChunkRepository,
    ) -> None:
        self._pipeline_repo = pipeline_repo
        self._review_repo = review_repo
        self._chunk_repo = chunk_repo

    async def execute(self) -> AnalyticsOut:
        """Return analytics snapshot (simplified — production would use Redis cache)."""
        pending_reviews = await self._review_repo.count_pending()
        active_runs = await self._pipeline_repo.count_active()
        return AnalyticsOut(
            overdue_review_count=pending_reviews,
        )
