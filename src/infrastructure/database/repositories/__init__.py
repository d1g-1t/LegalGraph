"""Concrete repository implementations — PostgreSQL via SQLAlchemy 2 async.

Implements all ports from src.domain.repositories.
Uses eager loading and batch fetching to avoid N+1.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import (
    AgentStep,
    ApiUser,
    EscalationCase,
    HumanReviewTask,
    KnowledgeChunk,
    KnowledgeDocument,
    LegalRequest,
    PipelineRun,
    RetrievedChunk,
)
from src.domain.repositories import (
    IAgentStepRepository,
    IEscalationRepository,
    IHumanReviewRepository,
    IKnowledgeChunkRepository,
    IKnowledgeDocumentRepository,
    ILegalRequestRepository,
    IPipelineRunRepository,
    IUserRepository,
)
from src.infrastructure.database.models import (
    AgentStepModel,
    ApiUserModel,
    EscalationCaseModel,
    HumanReviewTaskModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    LegalRequestModel,
    PipelineRunModel,
)


# ── Mapper helpers ──────────────────────────────────────

def _user_to_entity(m: ApiUserModel) -> ApiUser:
    return ApiUser(
        id=m.id, email=m.email, hashed_password=m.hashed_password,
        role=m.role, legal_entity_id=m.legal_entity_id,
        is_active=m.is_active, created_at=m.created_at, updated_at=m.updated_at,
    )


def _request_to_entity(m: LegalRequestModel) -> LegalRequest:
    return LegalRequest(
        id=m.id, requester_id=m.requester_id, legal_entity_id=m.legal_entity_id,
        channel=m.channel, priority=m.priority, raw_input=m.raw_input,
        submitted_at=m.submitted_at, status=m.status, created_at=m.created_at,
    )


def _run_to_entity(m: PipelineRunModel) -> PipelineRun:
    return PipelineRun(
        id=m.id, request_id=m.request_id, thread_id=m.thread_id,
        pipeline_status=m.pipeline_status, category=m.category, intent=m.intent,
        risk_level=m.risk_level,
        classifier_confidence=m.classifier_confidence,
        generated_response=m.generated_response, final_response=m.final_response,
        verification_passed=m.verification_passed,
        legal_accuracy_score=m.legal_accuracy_score,
        hallucination_detected=m.hallucination_detected,
        requires_human_review=m.requires_human_review,
        human_decision=m.human_decision,
        escalation_case_id=m.escalation_case_id,
        trace_id=m.trace_id, node_timings=m.node_timings or {},
        total_duration_ms=m.total_duration_ms,
        error_message=m.error_message, started_at=m.started_at,
        completed_at=m.completed_at, updated_at=m.updated_at,
    )


def _step_to_entity(m: AgentStepModel) -> AgentStep:
    return AgentStep(
        id=m.id, pipeline_run_id=m.pipeline_run_id, node_name=m.node_name,
        step_order=m.step_order, status=m.status,
        input_snapshot=m.input_snapshot, output_snapshot=m.output_snapshot,
        model_name=m.model_name, prompt_hash=m.prompt_hash,
        prompt_version=m.prompt_version, prompt_tokens=m.prompt_tokens,
        completion_tokens=m.completion_tokens, duration_ms=m.duration_ms,
        otel_span_id=m.otel_span_id, error_message=m.error_message,
        started_at=m.started_at, completed_at=m.completed_at,
    )


def _doc_to_entity(m: KnowledgeDocumentModel) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=m.id, legal_entity_id=m.legal_entity_id, is_global=m.is_global,
        document_name=m.document_name, document_type=m.document_type,
        category=m.category, source_path=m.source_path, checksum=m.checksum,
        total_chunks=m.total_chunks, metadata=m.metadata_ or {},
        created_at=m.created_at,
    )


def _review_to_entity(m: HumanReviewTaskModel) -> HumanReviewTask:
    return HumanReviewTask(
        id=m.id, pipeline_run_id=m.pipeline_run_id,
        assigned_reviewer_id=m.assigned_reviewer_id,
        priority=m.priority, reason=m.reason, status=m.status,
        deadline_at=m.deadline_at, decision=m.decision,
        comment=m.comment, edited_response=m.edited_response,
        created_at=m.created_at, decided_at=m.decided_at,
    )


def _escalation_to_entity(m: EscalationCaseModel) -> EscalationCase:
    return EscalationCase(
        id=m.id, pipeline_run_id=m.pipeline_run_id,
        category=m.category, risk_level=m.risk_level,
        priority=m.priority, reason=m.reason,
        assigned_lawyer_id=m.assigned_lawyer_id,
        context_package=m.context_package or {},
        status=m.status, resolution_note=m.resolution_note,
        sla_deadline=m.sla_deadline,
        created_at=m.created_at, resolved_at=m.resolved_at,
    )


# ── Repository implementations ──────────────────────────

class UserRepository(IUserRepository):
    """Concrete user repository backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> ApiUser | None:
        """Fetch user by primary key."""
        result = await self._session.get(ApiUserModel, user_id)
        return _user_to_entity(result) if result else None

    async def get_by_email(self, email: str) -> ApiUser | None:
        """Fetch user by email."""
        stmt = select(ApiUserModel).where(ApiUserModel.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _user_to_entity(row) if row else None

    async def create(self, user: ApiUser) -> ApiUser:
        """Insert a new user."""
        model = ApiUserModel(
            id=user.id, email=user.email, hashed_password=user.hashed_password,
            role=user.role, legal_entity_id=user.legal_entity_id,
            is_active=user.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        return user

    async def list_by_role(self, role: str, limit: int = 50, offset: int = 0) -> Sequence[ApiUser]:
        """List users filtered by role with pagination."""
        stmt = (
            select(ApiUserModel)
            .where(ApiUserModel.role == role, ApiUserModel.is_active.is_(True))
            .order_by(ApiUserModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [_user_to_entity(r) for r in result.scalars().all()]


class LegalRequestRepository(ILegalRequestRepository):
    """Concrete legal request repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, request: LegalRequest) -> LegalRequest:
        """Insert a new legal request."""
        model = LegalRequestModel(
            id=request.id, requester_id=request.requester_id,
            legal_entity_id=request.legal_entity_id,
            channel=request.channel, priority=request.priority,
            raw_input=request.raw_input, submitted_at=request.submitted_at,
            status=request.status,
        )
        self._session.add(model)
        await self._session.flush()
        return request

    async def get_by_id(self, request_id: uuid.UUID) -> LegalRequest | None:
        """Fetch a legal request with eager-loaded pipeline runs."""
        result = await self._session.get(LegalRequestModel, request_id)
        return _request_to_entity(result) if result else None

    async def list_requests(
        self,
        *,
        legal_entity_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[LegalRequest]:
        """List requests with optional filters and pagination."""
        stmt = select(LegalRequestModel).order_by(LegalRequestModel.submitted_at.desc())
        if legal_entity_id:
            stmt = stmt.where(LegalRequestModel.legal_entity_id == legal_entity_id)
        if status:
            stmt = stmt.where(LegalRequestModel.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_request_to_entity(r) for r in result.scalars().all()]

    async def update_status(self, request_id: uuid.UUID, status: str) -> None:
        """Update request status."""
        stmt = update(LegalRequestModel).where(LegalRequestModel.id == request_id).values(status=status)
        await self._session.execute(stmt)
        await self._session.flush()


class PipelineRunRepository(IPipelineRunRepository):
    """Concrete pipeline run repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, run: PipelineRun) -> PipelineRun:
        """Insert a new pipeline run."""
        model = PipelineRunModel(
            id=run.id, request_id=run.request_id, thread_id=run.thread_id,
            pipeline_status=run.pipeline_status,
        )
        self._session.add(model)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> PipelineRun | None:
        """Fetch a pipeline run with eager-loaded steps."""
        result = await self._session.get(PipelineRunModel, run_id)
        return _run_to_entity(result) if result else None

    async def get_by_thread_id(self, thread_id: str) -> PipelineRun | None:
        """Fetch pipeline run by LangGraph thread id."""
        stmt = select(PipelineRunModel).where(PipelineRunModel.thread_id == thread_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _run_to_entity(row) if row else None

    async def update(self, run: PipelineRun) -> None:
        """Update a pipeline run from domain entity."""
        stmt = (
            update(PipelineRunModel)
            .where(PipelineRunModel.id == run.id)
            .values(
                pipeline_status=run.pipeline_status,
                category=run.category,
                intent=run.intent,
                risk_level=run.risk_level,
                classifier_confidence=run.classifier_confidence,
                generated_response=run.generated_response,
                final_response=run.final_response,
                verification_passed=run.verification_passed,
                legal_accuracy_score=run.legal_accuracy_score,
                hallucination_detected=run.hallucination_detected,
                requires_human_review=run.requires_human_review,
                human_decision=run.human_decision,
                escalation_case_id=run.escalation_case_id,
                trace_id=run.trace_id,
                node_timings=run.node_timings,
                total_duration_ms=run.total_duration_ms,
                error_message=run.error_message,
                completed_at=run.completed_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def count_active(self) -> int:
        """Count currently running pipelines."""
        stmt = select(func.count()).where(PipelineRunModel.pipeline_status.in_(["PENDING", "RUNNING", "AWAITING_REVIEW"]))
        result = await self._session.execute(stmt)
        return result.scalar_one()


class AgentStepRepository(IAgentStepRepository):
    """Concrete agent step repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, step: AgentStep) -> AgentStep:
        """Insert a new agent step."""
        model = AgentStepModel(
            id=step.id, pipeline_run_id=step.pipeline_run_id,
            node_name=step.node_name, step_order=step.step_order,
            status=step.status, input_snapshot=step.input_snapshot,
            output_snapshot=step.output_snapshot, model_name=step.model_name,
            prompt_hash=step.prompt_hash, prompt_version=step.prompt_version,
            prompt_tokens=step.prompt_tokens,
            completion_tokens=step.completion_tokens,
            duration_ms=step.duration_ms, otel_span_id=step.otel_span_id,
            error_message=step.error_message,
            started_at=step.started_at, completed_at=step.completed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return step

    async def list_by_pipeline(self, pipeline_run_id: uuid.UUID) -> Sequence[AgentStep]:
        """List all steps for a pipeline run ordered by step_order."""
        stmt = (
            select(AgentStepModel)
            .where(AgentStepModel.pipeline_run_id == pipeline_run_id)
            .order_by(AgentStepModel.step_order)
        )
        result = await self._session.execute(stmt)
        return [_step_to_entity(r) for r in result.scalars().all()]


class KnowledgeDocumentRepository(IKnowledgeDocumentRepository):
    """Concrete knowledge document repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, doc: KnowledgeDocument) -> KnowledgeDocument:
        """Insert a new knowledge document."""
        model = KnowledgeDocumentModel(
            id=doc.id, legal_entity_id=doc.legal_entity_id, is_global=doc.is_global,
            document_name=doc.document_name, document_type=doc.document_type,
            category=doc.category, source_path=doc.source_path,
            checksum=doc.checksum, total_chunks=doc.total_chunks,
            metadata_=doc.metadata,
        )
        self._session.add(model)
        await self._session.flush()
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> KnowledgeDocument | None:
        """Fetch a document by id."""
        result = await self._session.get(KnowledgeDocumentModel, doc_id)
        return _doc_to_entity(result) if result else None

    async def list_documents(self, limit: int = 50, offset: int = 0) -> Sequence[KnowledgeDocument]:
        """List documents with pagination."""
        stmt = select(KnowledgeDocumentModel).order_by(KnowledgeDocumentModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_doc_to_entity(r) for r in result.scalars().all()]

    async def delete(self, doc_id: uuid.UUID) -> None:
        """Delete a document and its chunks (cascade)."""
        stmt = delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == doc_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def update_chunk_count(self, doc_id: uuid.UUID, count: int) -> None:
        """Update total_chunks after ingestion."""
        stmt = update(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == doc_id).values(total_chunks=count)
        await self._session.execute(stmt)
        await self._session.flush()

    async def count_total(self) -> int:
        """Count total documents."""
        result = await self._session.execute(select(func.count(KnowledgeDocumentModel.id)))
        return result.scalar_one()


class KnowledgeChunkRepository(IKnowledgeChunkRepository):
    """Concrete knowledge chunk repository with pgvector search."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(self, chunks: Sequence[KnowledgeChunk]) -> int:
        """Bulk insert chunks, skipping existing by content_hash."""
        created = 0
        for chunk in chunks:
            exists = await self.exists_by_hash(chunk.content_hash)
            if exists:
                continue
            model = KnowledgeChunkModel(
                id=chunk.id, document_id=chunk.document_id,
                legal_entity_id=chunk.legal_entity_id, is_global=chunk.is_global,
                document_name=chunk.document_name, document_type=chunk.document_type,
                category=chunk.category, chunk_index=chunk.chunk_index,
                total_chunks=chunk.total_chunks, section_header=chunk.section_header,
                page_number=chunk.page_number, content=chunk.content,
                content_hash=chunk.content_hash, metadata_=chunk.metadata,
                embedding=chunk.embedding,
            )
            self._session.add(model)
            created += 1
        await self._session.flush()
        return created

    async def semantic_search(
        self,
        embedding: list[float],
        *,
        legal_entity_id: uuid.UUID | None = None,
        category: str | None = None,
        top_k: int = 8,
    ) -> Sequence[RetrievedChunk]:
        """Vector cosine distance search with tenant isolation."""
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        filters = ["1=1"]
        params: dict = {"emb": embedding_str, "top_k": top_k}

        if legal_entity_id:
            filters.append("(legal_entity_id = :entity_id OR is_global = true)")
            params["entity_id"] = str(legal_entity_id)
        if category:
            filters.append("category = :category")
            params["category"] = category

        where_clause = " AND ".join(filters)
        query = text(f"""
            SELECT id, document_name, section_header, page_number, content, category,
                   1 - (embedding <=> :emb::vector) AS score
            FROM knowledge_chunks
            WHERE {where_clause}
            ORDER BY embedding <=> :emb::vector
            LIMIT :top_k
        """)
        result = await self._session.execute(query, params)
        rows = result.fetchall()
        return [
            RetrievedChunk(
                chunk_id=row[0], document_name=row[1],
                section_header=row[2], page_number=row[3],
                content=row[4], category=row[5], score=float(row[6]),
            )
            for row in rows
        ]

    async def fulltext_search(
        self,
        query: str,
        *,
        legal_entity_id: uuid.UUID | None = None,
        top_k: int = 8,
    ) -> Sequence[RetrievedChunk]:
        """Full-text search fallback using Russian tsvector."""
        filters = ["to_tsvector('russian', content) @@ plainto_tsquery('russian', :query)"]
        params: dict = {"query": query, "top_k": top_k}

        if legal_entity_id:
            filters.append("(legal_entity_id = :entity_id OR is_global = true)")
            params["entity_id"] = str(legal_entity_id)

        where_clause = " AND ".join(filters)
        sql = text(f"""
            SELECT id, document_name, section_header, page_number, content, category,
                   ts_rank(to_tsvector('russian', content), plainto_tsquery('russian', :query)) AS score
            FROM knowledge_chunks
            WHERE {where_clause}
            ORDER BY score DESC
            LIMIT :top_k
        """)
        result = await self._session.execute(sql, params)
        rows = result.fetchall()
        return [
            RetrievedChunk(
                chunk_id=row[0], document_name=row[1],
                section_header=row[2], page_number=row[3],
                content=row[4], category=row[5], score=float(row[6]),
            )
            for row in rows
        ]

    async def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Delete all chunks for a document."""
        stmt = delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == document_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def exists_by_hash(self, content_hash: str) -> bool:
        """Check if a chunk with this content hash already exists."""
        stmt = select(func.count()).where(KnowledgeChunkModel.content_hash == content_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def count_total(self) -> int:
        """Count total chunks."""
        result = await self._session.execute(select(func.count(KnowledgeChunkModel.id)))
        return result.scalar_one()


class HumanReviewRepository(IHumanReviewRepository):
    """Concrete HITL repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, task: HumanReviewTask) -> HumanReviewTask:
        """Insert a new review task."""
        model = HumanReviewTaskModel(
            id=task.id, pipeline_run_id=task.pipeline_run_id,
            assigned_reviewer_id=task.assigned_reviewer_id,
            priority=task.priority, reason=task.reason,
            status=task.status, deadline_at=task.deadline_at,
        )
        self._session.add(model)
        await self._session.flush()
        return task

    async def get_by_pipeline(self, pipeline_run_id: uuid.UUID) -> HumanReviewTask | None:
        """Fetch review task by pipeline run."""
        stmt = select(HumanReviewTaskModel).where(HumanReviewTaskModel.pipeline_run_id == pipeline_run_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _review_to_entity(row) if row else None

    async def list_pending(self, limit: int = 20, offset: int = 0) -> Sequence[HumanReviewTask]:
        """List pending review tasks ordered by deadline."""
        stmt = (
            select(HumanReviewTaskModel)
            .where(HumanReviewTaskModel.status == "PENDING")
            .order_by(HumanReviewTaskModel.deadline_at.asc())
            .limit(limit).offset(offset)
        )
        result = await self._session.execute(stmt)
        return [_review_to_entity(r) for r in result.scalars().all()]

    async def update(self, task: HumanReviewTask) -> None:
        """Update review task from entity."""
        stmt = (
            update(HumanReviewTaskModel)
            .where(HumanReviewTaskModel.id == task.id)
            .values(
                assigned_reviewer_id=task.assigned_reviewer_id,
                status=task.status, decision=task.decision,
                comment=task.comment, edited_response=task.edited_response,
                decided_at=task.decided_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def count_pending(self) -> int:
        """Count pending review tasks."""
        stmt = select(func.count()).where(HumanReviewTaskModel.status == "PENDING")
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def list_overdue(self, now: datetime) -> Sequence[HumanReviewTask]:
        """List review tasks past deadline."""
        stmt = (
            select(HumanReviewTaskModel)
            .where(
                HumanReviewTaskModel.status == "PENDING",
                HumanReviewTaskModel.deadline_at < now,
            )
            .order_by(HumanReviewTaskModel.deadline_at.asc())
        )
        result = await self._session.execute(stmt)
        return [_review_to_entity(r) for r in result.scalars().all()]

    async def get_next_reviewer_id(self, role: str) -> uuid.UUID | None:
        """Round-robin: select least-recently-assigned reviewer."""
        stmt = text("""
            SELECT u.id FROM api_users u
            LEFT JOIN human_review_tasks t ON t.assigned_reviewer_id = u.id AND t.status = 'PENDING'
            WHERE u.role = :role AND u.is_active = true
            GROUP BY u.id
            ORDER BY COUNT(t.id) ASC, u.created_at ASC
            LIMIT 1
        """)
        result = await self._session.execute(stmt, {"role": role})
        row = result.first()
        return row[0] if row else None


class EscalationRepository(IEscalationRepository):
    """Concrete escalation repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, case: EscalationCase) -> EscalationCase:
        """Insert an escalation case."""
        model = EscalationCaseModel(
            id=case.id, pipeline_run_id=case.pipeline_run_id,
            category=case.category, risk_level=case.risk_level,
            priority=case.priority, reason=case.reason,
            assigned_lawyer_id=case.assigned_lawyer_id,
            context_package=case.context_package,
            status=case.status, sla_deadline=case.sla_deadline,
        )
        self._session.add(model)
        await self._session.flush()
        return case

    async def get_by_id(self, case_id: uuid.UUID) -> EscalationCase | None:
        """Fetch an escalation case."""
        result = await self._session.get(EscalationCaseModel, case_id)
        return _escalation_to_entity(result) if result else None

    async def list_cases(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[EscalationCase]:
        """List escalation cases with optional status filter."""
        stmt = select(EscalationCaseModel).order_by(EscalationCaseModel.created_at.desc())
        if status:
            stmt = stmt.where(EscalationCaseModel.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [_escalation_to_entity(r) for r in result.scalars().all()]

    async def update(self, case: EscalationCase) -> None:
        """Update escalation case."""
        stmt = (
            update(EscalationCaseModel)
            .where(EscalationCaseModel.id == case.id)
            .values(
                assigned_lawyer_id=case.assigned_lawyer_id,
                status=case.status, resolution_note=case.resolution_note,
                resolved_at=case.resolved_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
