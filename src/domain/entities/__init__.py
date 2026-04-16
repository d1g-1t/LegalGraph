"""Domain entities — pure data classes, NO ORM dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class LegalRequest:
    """Incoming legal request from a user."""

    id: UUID = field(default_factory=uuid4)
    requester_id: UUID = field(default_factory=uuid4)
    legal_entity_id: UUID = field(default_factory=uuid4)
    channel: str = "API"
    priority: str = "NORMAL"
    raw_input: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    status: str = "NEW"
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))


@dataclass
class PipelineRun:
    """A single execution of the multi-agent pipeline."""

    id: UUID = field(default_factory=uuid4)
    request_id: UUID = field(default_factory=uuid4)
    thread_id: str = ""
    pipeline_status: str = "PENDING"
    category: str | None = None
    intent: str | None = None
    risk_level: str | None = None
    classifier_confidence: Decimal | None = None
    generated_response: str | None = None
    final_response: str | None = None
    verification_passed: bool | None = None
    legal_accuracy_score: Decimal | None = None
    hallucination_detected: bool | None = None
    requires_human_review: bool = False
    human_decision: str | None = None
    escalation_case_id: UUID | None = None
    trace_id: str | None = None
    node_timings: dict[str, float] = field(default_factory=dict)
    total_duration_ms: int | None = None
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))


@dataclass
class AgentStep:
    """Record of a single agent node execution."""

    id: UUID = field(default_factory=uuid4)
    pipeline_run_id: UUID = field(default_factory=uuid4)
    node_name: str = ""
    step_order: int = 0
    status: str = "PENDING"
    input_snapshot: dict | None = None
    output_snapshot: dict | None = None
    model_name: str | None = None
    prompt_hash: str | None = None
    prompt_version: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_ms: int | None = None
    otel_span_id: str | None = None
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    completed_at: datetime | None = None


@dataclass
class KnowledgeDocument:
    """Uploaded document for the RAG knowledge base."""

    id: UUID = field(default_factory=uuid4)
    legal_entity_id: UUID | None = None
    is_global: bool = False
    document_name: str = ""
    document_type: str = ""
    category: str | None = None
    source_path: str = ""
    checksum: str = ""
    total_chunks: int = 0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))


@dataclass
class KnowledgeChunk:
    """A chunk of a knowledge document with its embedding."""

    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    legal_entity_id: UUID | None = None
    is_global: bool = False
    document_name: str = ""
    document_type: str = ""
    category: str | None = None
    chunk_index: int = 0
    total_chunks: int = 0
    section_header: str | None = None
    page_number: int | None = None
    content: str = ""
    content_hash: str = ""
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))


@dataclass
class RetrievedChunk:
    """A chunk returned from RAG search with similarity score."""

    chunk_id: UUID = field(default_factory=uuid4)
    document_name: str = ""
    section_header: str | None = None
    page_number: int | None = None
    content: str = ""
    score: float = 0.0
    category: str | None = None


@dataclass
class HumanReviewTask:
    """Pending human-in-the-loop review task."""

    id: UUID = field(default_factory=uuid4)
    pipeline_run_id: UUID = field(default_factory=uuid4)
    assigned_reviewer_id: UUID | None = None
    priority: str = "NORMAL"
    reason: str = ""
    status: str = "PENDING"
    deadline_at: datetime | None = None
    decision: str | None = None
    comment: str | None = None
    edited_response: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    decided_at: datetime | None = None


@dataclass
class EscalationCase:
    """Escalated case requiring lawyer attention."""

    id: UUID = field(default_factory=uuid4)
    pipeline_run_id: UUID = field(default_factory=uuid4)
    category: str = ""
    risk_level: str = ""
    priority: str = "NORMAL"
    reason: str = ""
    assigned_lawyer_id: UUID | None = None
    context_package: dict = field(default_factory=dict)
    status: str = "OPEN"
    resolution_note: str | None = None
    sla_deadline: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    resolved_at: datetime | None = None


@dataclass
class ApiUser:
    """Platform user."""

    id: UUID = field(default_factory=uuid4)
    email: str = ""
    hashed_password: str = ""
    role: str = "VIEWER"
    legal_entity_id: UUID | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
