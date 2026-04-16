"""Pipeline state — strongly typed TypedDict for LangGraph.

Every node reads / writes only the fields it needs.
"""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID


class RetrievedChunkState(TypedDict):
    """Serialisable chunk for graph state."""
    chunk_id: str
    document_name: str
    section_header: str | None
    page_number: int | None
    content: str
    score: float
    category: str | None


class PipelineState(TypedDict, total=False):
    """Full pipeline state carried through the LangGraph."""

    # ── Identity ──
    request_id: str
    pipeline_run_id: str
    requester_id: str
    legal_entity_id: str
    raw_input: str
    submitted_at: str
    current_node: str

    # ── Classifier ──
    category: str | None
    intent: str | None
    risk_level: str | None
    classifier_confidence: float | None
    classifier_reasoning: str | None
    extracted_entities: list[str]

    # ── Retriever ──
    retrieval_query: str | None
    retrieved_chunks: list[RetrievedChunkState]
    retrieval_avg_score: float | None

    # ── Generator ──
    generation_retry_count: int
    generated_response: str | None
    generation_model: str | None
    generation_prompt_tokens: int | None
    generation_completion_tokens: int | None
    generation_latency_ms: float | None

    # ── Verifier ──
    verification_passed: bool | None
    hallucination_detected: bool | None
    legal_accuracy_score: float | None
    verification_issues: list[str]

    # ── HITL ──
    requires_human_review: bool
    human_review_reason: str | None
    human_review_task_id: str | None
    human_decision: str | None
    human_edited_response: str | None

    # ── Escalation ──
    escalation_required: bool
    escalation_reason: str | None
    escalation_case_id: str | None

    # ── Final ──
    final_response: str | None
    final_status: str

    # ── Observability ──
    trace_id: str | None
    node_timings: dict[str, float]
    errors: list[str]
