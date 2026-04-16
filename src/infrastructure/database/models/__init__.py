"""SQLAlchemy 2 ORM models — all tables for LegalOpsAI-Pipeline.

Uses server-default UTC timestamps, proper indexes, and pgvector column.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


# ── Helper ──────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(tz=__import__("datetime").timezone.utc)


# ── Users ───────────────────────────────────────────────
class ApiUserModel(Base):
    """ORM model for api_users table."""

    __tablename__ = "api_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="VIEWER")
    legal_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Legal Requests ──────────────────────────────────────
class LegalRequestModel(Base):
    """ORM model for legal_requests table."""

    __tablename__ = "legal_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("api_users.id"), nullable=False)
    legal_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="API")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pipeline_runs: Mapped[list["PipelineRunModel"]] = relationship(back_populates="request", lazy="selectin")


# ── Pipeline Runs ───────────────────────────────────────
class PipelineRunModel(Base):
    """ORM model for pipeline_runs table."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_requests.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    pipeline_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    classifier_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    generated_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    legal_accuracy_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    hallucination_detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    human_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    escalation_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    node_timings: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    request: Mapped["LegalRequestModel"] = relationship(back_populates="pipeline_runs", lazy="selectin")
    steps: Mapped[list["AgentStepModel"]] = relationship(back_populates="pipeline_run", lazy="selectin")


# ── Agent Steps ─────────────────────────────────────────
class AgentStepModel(Base):
    """ORM model for agent_steps table."""

    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    node_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    otel_span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pipeline_run: Mapped["PipelineRunModel"] = relationship(back_populates="steps")


# ── Knowledge Documents ─────────────────────────────────
class KnowledgeDocumentModel(Base):
    """ORM model for knowledge_documents table."""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["KnowledgeChunkModel"]] = relationship(back_populates="document", cascade="all, delete-orphan")


# ── Knowledge Chunks ────────────────────────────────────
class KnowledgeChunkModel(Base):
    """ORM model for knowledge_chunks table with pgvector embedding."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id"), nullable=False, index=True
    )
    legal_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    section_header: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    embedding = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["KnowledgeDocumentModel"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_embedding_hnsw", embedding, postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_chunks_content_fts", func.to_tsvector("russian", "content"), postgresql_using="gin"),
        Index("ix_chunks_metadata_gin", "metadata", postgresql_using="gin"),
    )


# ── Human Review Tasks ──────────────────────────────────
class HumanReviewTaskModel(Base):
    """ORM model for human_review_tasks table."""

    __tablename__ = "human_review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_users.id"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Escalation Cases ────────────────────────────────────
class EscalationCaseModel(Base):
    """ORM model for escalation_cases table."""

    __tablename__ = "escalation_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_lawyer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_users.id"), nullable=True
    )
    context_package: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
