"""Data Transfer Objects — Pydantic v2 models for API requests/responses.

No ORM, no domain leakage.  These are the only objects routers touch.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Auth ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Login credentials."""
    email: EmailStr
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    """Pair of tokens returned after auth."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class UserOut(BaseModel):
    """Public user representation."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    role: str
    legal_entity_id: UUID | None = None
    is_active: bool
    created_at: datetime


# ── Requests ────────────────────────────────────────────

class SubmitRequestIn(BaseModel):
    """Body for submitting a legal request."""
    raw_input: str = Field(min_length=10, max_length=10000, description="Текст юридического запроса")
    channel: str = "API"
    priority: str = "NORMAL"


class RequestOut(BaseModel):
    """Legal request summary."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    requester_id: UUID
    legal_entity_id: UUID
    channel: str
    priority: str
    raw_input: str
    submitted_at: datetime
    status: str


class SubmitRequestOut(BaseModel):
    """Response after request submission."""
    request_id: UUID
    pipeline_run_id: UUID
    message: str = "Запрос принят в обработку"


# ── Pipeline ────────────────────────────────────────────

class PipelineRunOut(BaseModel):
    """Pipeline run details."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_id: UUID
    thread_id: str
    pipeline_status: str
    category: str | None = None
    intent: str | None = None
    risk_level: str | None = None
    classifier_confidence: float | None = None
    generated_response: str | None = None
    final_response: str | None = None
    verification_passed: bool | None = None
    legal_accuracy_score: float | None = None
    hallucination_detected: bool | None = None
    requires_human_review: bool = False
    human_decision: str | None = None
    trace_id: str | None = None
    node_timings: dict[str, float] = {}
    total_duration_ms: int | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AgentStepOut(BaseModel):
    """Agent step details."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    node_name: str
    step_order: int
    status: str
    model_name: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


# ── Human Review ────────────────────────────────────────

class HumanReviewOut(BaseModel):
    """Human review task representation."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pipeline_run_id: UUID
    assigned_reviewer_id: UUID | None = None
    priority: str
    reason: str
    status: str
    deadline_at: datetime | None = None
    decision: str | None = None
    comment: str | None = None
    edited_response: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ReviewDecisionIn(BaseModel):
    """Reviewer's decision payload."""
    decision: str = Field(pattern="^(APPROVED|EDITED|REJECTED)$")
    comment: str | None = None
    edited_response: str | None = None


# ── Escalation ──────────────────────────────────────────

class EscalationOut(BaseModel):
    """Escalation case representation."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pipeline_run_id: UUID
    category: str
    risk_level: str
    priority: str
    reason: str
    assigned_lawyer_id: UUID | None = None
    status: str
    resolution_note: str | None = None
    sla_deadline: datetime | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class AssignLawyerIn(BaseModel):
    """Assign a lawyer to an escalation case."""
    lawyer_id: UUID


class ResolveEscalationIn(BaseModel):
    """Resolve an escalation case."""
    resolution_note: str = Field(min_length=5)


# ── Knowledge ───────────────────────────────────────────

class KnowledgeDocOut(BaseModel):
    """Knowledge document representation."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_name: str
    document_type: str
    category: str | None = None
    is_global: bool
    total_chunks: int
    created_at: datetime


class SearchRequest(BaseModel):
    """Search query for RAG."""
    query: str = Field(min_length=3, max_length=2000)
    category: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchChunkOut(BaseModel):
    """A single search result chunk."""
    chunk_id: UUID
    document_name: str
    section_header: str | None = None
    page_number: int | None = None
    content: str
    score: float
    category: str | None = None


class SearchResponse(BaseModel):
    """RAG search response."""
    query: str
    total: int
    chunks: list[SearchChunkOut]


class KnowledgeStatsOut(BaseModel):
    """Knowledge base statistics."""
    total_documents: int
    total_chunks: int


# ── Analytics ───────────────────────────────────────────

class AnalyticsOut(BaseModel):
    """Analytics aggregates."""
    total_requests_1d: int = 0
    total_requests_7d: int = 0
    total_requests_30d: int = 0
    completion_rate: float = 0.0
    escalation_rate: float = 0.0
    human_review_rate: float = 0.0
    failure_rate: float = 0.0
    category_distribution: dict[str, int] = {}
    avg_latency_by_node: dict[str, float] = {}
    avg_retrieval_score: float = 0.0
    avg_accuracy_score: float = 0.0
    top_escalation_reasons: list[dict[str, int | str]] = []
    top_verifier_issues: list[str] = []
    overdue_review_count: int = 0


# ── Health ──────────────────────────────────────────────

class HealthOut(BaseModel):
    """Health check result."""
    status: str
    database: str = "unknown"
    redis: str = "unknown"
    ollama: str = "unknown"


# ── Pagination ──────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """Generic paginated wrapper."""
    items: list = []
    total: int = 0
    limit: int = 20
    offset: int = 0
