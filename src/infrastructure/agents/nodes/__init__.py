"""Agent nodes — each node is a pure function State → Partial[State].

Nodes emit OpenTelemetry spans, record Prometheus metrics, and persist step records.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.core.config import get_settings
from src.core.telemetry import get_tracer
from src.domain.services import RiskPolicyService
from src.infrastructure.agents.prompts import load_prompt, prompt_hash, prompt_version
from src.infrastructure.agents.state import PipelineState, RetrievedChunkState
from src.infrastructure.llm import OllamaLLMService
from src.infrastructure.observability import (
    AGENT_NODE_DURATION,
    AGENT_NODE_ERRORS,
    CLASSIFIER_PREDICTIONS,
    ESCALATIONS_TOTAL,
    HITL_TASKS_CREATED,
    LLM_LATENCY,
    LLM_REQUESTS_TOTAL,
    LLM_TOKENS_TOTAL,
    RAG_CHUNKS_RETRIEVED,
    RAG_SEARCH_LATENCY,
    RAG_SEARCHES_TOTAL,
    VERIFIER_CHECKS_TOTAL,
    VERIFIER_FAILURES,
)

logger = structlog.get_logger(__name__)
tracer = get_tracer("legalops.agents")


# ── Helpers ─────────────────────────────────────────────

def _safe_json_parse(text: str) -> dict[str, Any] | None:
    """Try to parse JSON from LLM output, handle markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── Classifier Node ─────────────────────────────────────

async def classifier_node(state: PipelineState) -> dict[str, Any]:
    """Classify the legal request: category, intent, risk, confidence."""
    start = time.perf_counter()
    settings = get_settings()
    llm = OllamaLLMService()

    system_prompt = load_prompt("classifier_prompt")
    p_hash = prompt_hash(system_prompt)
    p_version = prompt_version("classifier_prompt")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state.get("raw_input", "")},
    ]

    result: dict[str, Any] | None = None
    with tracer.start_as_current_span("classifier_node") as span:
        span.set_attribute("pipeline_run_id", state.get("pipeline_run_id", ""))
        span.set_attribute("request_id", state.get("request_id", ""))
        span.set_attribute("prompt_hash", p_hash)
        span.set_attribute("prompt_version", p_version)

        for attempt in range(2):
            LLM_REQUESTS_TOTAL.labels(model=settings.ollama_chat_model, node_name="classifier").inc()
            resp = await llm.chat(messages, format_json=True)
            LLM_LATENCY.labels(model=settings.ollama_chat_model).observe(resp.get("_latency_ms", 0) / 1000)
            LLM_TOKENS_TOTAL.labels(model=settings.ollama_chat_model, token_type="prompt").inc(resp.get("prompt_eval_count", 0))
            LLM_TOKENS_TOTAL.labels(model=settings.ollama_chat_model, token_type="completion").inc(resp.get("eval_count", 0))
            content = resp.get("message", {}).get("content", "")
            result = _safe_json_parse(content)
            if result:
                break
            logger.warning("classifier_json_parse_retry", attempt=attempt + 1)

        elapsed_s = time.perf_counter() - start
        elapsed = elapsed_s * 1000
        AGENT_NODE_DURATION.labels(node_name="classifier").observe(elapsed_s)

        if not result:
            logger.error("classifier_failed_to_parse")
            AGENT_NODE_ERRORS.labels(node_name="classifier", error_type="json_parse").inc()
            span.set_attribute("error", True)
            return {
                "current_node": "classifier",
                "category": "OTHER",
                "intent": "Не удалось классифицировать",
                "risk_level": "HIGH",
                "classifier_confidence": 0.0,
                "classifier_reasoning": "JSON parse failure",
                "extracted_entities": [],
                "requires_human_review": True,
                "node_timings": {**state.get("node_timings", {}), "classifier": elapsed},
                "errors": [*state.get("errors", []), "classifier: JSON parse failure"],
            }

        category = result.get("category", "OTHER")
        risk_level = result.get("risk_level", "MEDIUM")
        confidence = float(result.get("confidence", 0.5))
        requires_human = bool(result.get("requires_human_review", False))

        # Policy overrides
        if RiskPolicyService.needs_immediate_escalation(risk_level, confidence):
            pass  # routing handled in graph conditional edges
        if RiskPolicyService.needs_human_review(risk_level, requires_human):
            requires_human = True

        CLASSIFIER_PREDICTIONS.labels(category=category, risk_level=risk_level).inc()
        span.set_attribute("category", category)
        span.set_attribute("risk_level", risk_level)
        span.set_attribute("confidence", confidence)

    logger.info(
        "classifier_completed",
        category=category,
        risk_level=risk_level,
        confidence=confidence,
    )

    return {
        "current_node": "classifier",
        "category": category,
        "intent": result.get("intent", ""),
        "risk_level": risk_level,
        "classifier_confidence": confidence,
        "classifier_reasoning": result.get("reasoning", ""),
        "extracted_entities": result.get("extracted_entities", []),
        "requires_human_review": requires_human,
        "node_timings": {**state.get("node_timings", {}), "classifier": elapsed},
    }


# ── Retriever Node ──────────────────────────────────────

async def retriever_node(state: PipelineState) -> dict[str, Any]:
    """Reformulate query + vector search + MMR rerank."""
    start = time.perf_counter()
    settings = get_settings()
    llm = OllamaLLMService()

    with tracer.start_as_current_span("retriever_node") as span:
        span.set_attribute("pipeline_run_id", state.get("pipeline_run_id", ""))
        span.set_attribute("category", state.get("category", ""))

        # Query rewrite
        rewrite_prompt = load_prompt("retriever_rewrite_prompt")
        messages = [
            {"role": "system", "content": rewrite_prompt},
            {"role": "user", "content": state.get("raw_input", "")},
        ]
        LLM_REQUESTS_TOTAL.labels(model=settings.ollama_chat_model, node_name="retriever").inc()
        resp = await llm.chat(messages)
        LLM_LATENCY.labels(model=settings.ollama_chat_model).observe(resp.get("_latency_ms", 0) / 1000)
        rewritten_query = resp.get("message", {}).get("content", state.get("raw_input", ""))

        # Import here to avoid circular imports at module level
        from src.infrastructure.database import build_session_factory
        from src.infrastructure.database.repositories import KnowledgeChunkRepository
        from src.infrastructure.rag import RAGService
        from src.infrastructure.database.repositories import KnowledgeDocumentRepository

        search_start = time.perf_counter()
        session_factory = build_session_factory()
        async with session_factory() as session:
            chunk_repo = KnowledgeChunkRepository(session)
            doc_repo = KnowledgeDocumentRepository(session)
            rag = RAGService(doc_repo, chunk_repo, llm)

            entity_id = state.get("legal_entity_id")
            legal_entity_uuid = UUID(entity_id) if entity_id else None

            chunks = await rag.search(
                rewritten_query,
                legal_entity_id=legal_entity_uuid,
                category=state.get("category"),
            )

        RAG_SEARCHES_TOTAL.inc()
        RAG_SEARCH_LATENCY.observe(time.perf_counter() - search_start)
        RAG_CHUNKS_RETRIEVED.observe(len(chunks))

        elapsed_s = time.perf_counter() - start
        elapsed = elapsed_s * 1000
        AGENT_NODE_DURATION.labels(node_name="retriever").observe(elapsed_s)
        avg_score = sum(c.score for c in chunks) / len(chunks) if chunks else 0.0

        span.set_attribute("chunks_found", len(chunks))
        span.set_attribute("avg_score", round(avg_score, 4))

    retrieved: list[RetrievedChunkState] = [
        {
            "chunk_id": str(c.chunk_id),
            "document_name": c.document_name,
            "section_header": c.section_header,
            "page_number": c.page_number,
            "content": c.content,
            "score": c.score,
            "category": c.category,
        }
        for c in chunks
    ]

    logger.info("retriever_completed", chunks_found=len(chunks), avg_score=round(avg_score, 3))

    return {
        "current_node": "retriever",
        "retrieval_query": rewritten_query,
        "retrieved_chunks": retrieved,
        "retrieval_avg_score": avg_score,
        "node_timings": {**state.get("node_timings", {}), "retriever": elapsed},
    }


# ── Generator Node ──────────────────────────────────────

PROMPT_MAP = {
    "CONTRACT_REVIEW": "generator_contract_review_prompt",
    "CONTRACT_DRAFT": "generator_contract_review_prompt",
    "LEGAL_FAQ": "generator_faq_prompt",
    "COMPLIANCE_CHECK": "generator_compliance_prompt",
    "COURT_PREPARATION": "generator_litigation_prompt",
    "CORPORATE_ACTION": "generator_corporate_prompt",
    "DATA_PRIVACY": "generator_compliance_prompt",
    "OTHER": "generator_faq_prompt",
}


async def generator_node(state: PipelineState) -> dict[str, Any]:
    """Generate grounded response based on retrieved context."""
    start = time.perf_counter()
    settings = get_settings()
    llm = OllamaLLMService()

    category = state.get("category", "OTHER")
    prompt_name = PROMPT_MAP.get(category, "generator_faq_prompt")
    system_template = load_prompt(prompt_name)

    # Build context from chunks
    chunks = state.get("retrieved_chunks", [])
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk.get('document_name', 'N/A')}"
        if chunk.get("section_header"):
            source += f" — {chunk['section_header']}"
        source += "]"
        context_parts.append(f"Источник {i} {source}:\n{chunk.get('content', '')}")

    context = "\n\n---\n\n".join(context_parts) if context_parts else "Контекст не найден."
    system_prompt = system_template.replace("{context}", context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state.get("raw_input", "")},
    ]

    with tracer.start_as_current_span("generator_node") as span:
        span.set_attribute("pipeline_run_id", state.get("pipeline_run_id", ""))
        span.set_attribute("category", category)
        span.set_attribute("prompt_name", prompt_name)

        LLM_REQUESTS_TOTAL.labels(model=settings.ollama_chat_model, node_name="generator").inc()
        resp = await llm.chat(messages)
        LLM_LATENCY.labels(model=settings.ollama_chat_model).observe(resp.get("_latency_ms", 0) / 1000)
        LLM_TOKENS_TOTAL.labels(model=settings.ollama_chat_model, token_type="prompt").inc(resp.get("prompt_eval_count", 0))
        LLM_TOKENS_TOTAL.labels(model=settings.ollama_chat_model, token_type="completion").inc(resp.get("eval_count", 0))

        generated = resp.get("message", {}).get("content", "")
        elapsed_s = time.perf_counter() - start
        elapsed = elapsed_s * 1000
        AGENT_NODE_DURATION.labels(node_name="generator").observe(elapsed_s)

        span.set_attribute("generation_tokens", resp.get("eval_count", 0))
        span.set_attribute("latency_ms", round(elapsed, 1))

    retry_count = state.get("generation_retry_count", 0)

    logger.info("generator_completed", category=category, latency_ms=round(elapsed, 1))

    return {
        "current_node": "generator",
        "generated_response": generated,
        "generation_model": resp.get("_model", settings.ollama_chat_model),
        "generation_prompt_tokens": resp.get("prompt_eval_count"),
        "generation_completion_tokens": resp.get("eval_count"),
        "generation_latency_ms": elapsed,
        "generation_retry_count": retry_count + 1,
        "node_timings": {**state.get("node_timings", {}), "generator": elapsed},
    }


# ── Verifier Node ───────────────────────────────────────

async def verifier_node(state: PipelineState) -> dict[str, Any]:
    """Verify generated response: hallucination check + accuracy scoring."""
    start = time.perf_counter()
    settings = get_settings()
    llm = OllamaLLMService()
    issues: list[str] = []

    generated = state.get("generated_response", "")
    chunks = state.get("retrieved_chunks", [])
    sources_text = "\n\n".join(
        f"[{c.get('document_name', '')}]: {c.get('content', '')}" for c in chunks
    )

    with tracer.start_as_current_span("verifier_node") as span:
        span.set_attribute("pipeline_run_id", state.get("pipeline_run_id", ""))

        # 1. Hallucination detection
        VERIFIER_CHECKS_TOTAL.labels(check_type="hallucination").inc()
        hall_prompt = load_prompt("verifier_hallucination_prompt")
        hall_prompt = hall_prompt.replace("{generated_response}", generated).replace("{sources}", sources_text)
        LLM_REQUESTS_TOTAL.labels(model=settings.ollama_chat_model, node_name="verifier").inc()
        hall_resp = await llm.chat(
            [{"role": "system", "content": hall_prompt}, {"role": "user", "content": "Проверь ответ."}],
            format_json=True,
        )
        LLM_LATENCY.labels(model=settings.ollama_chat_model).observe(hall_resp.get("_latency_ms", 0) / 1000)
        hall_content = hall_resp.get("message", {}).get("content", "")
        hall_result = _safe_json_parse(hall_content) or {}
        hallucination_detected = bool(hall_result.get("hallucination_detected", False))
        if hallucination_detected:
            issues.append("Обнаружены неподтверждённые утверждения")
            VERIFIER_FAILURES.labels(check_type="hallucination").inc()

        # 2. Accuracy scoring
        VERIFIER_CHECKS_TOTAL.labels(check_type="accuracy").inc()
        acc_prompt = load_prompt("verifier_accuracy_prompt")
        acc_prompt = (
            acc_prompt
            .replace("{generated_response}", generated)
            .replace("{question}", state.get("raw_input", ""))
            .replace("{sources}", sources_text)
        )
        LLM_REQUESTS_TOTAL.labels(model=settings.ollama_chat_model, node_name="verifier").inc()
        acc_resp = await llm.chat(
            [{"role": "system", "content": acc_prompt}, {"role": "user", "content": "Оцени ответ."}],
            format_json=True,
        )
        LLM_LATENCY.labels(model=settings.ollama_chat_model).observe(acc_resp.get("_latency_ms", 0) / 1000)
        acc_content = acc_resp.get("message", {}).get("content", "")
        acc_result = _safe_json_parse(acc_content) or {}
        accuracy_score = float(acc_result.get("accuracy_score", 0.5))
        issues.extend(acc_result.get("issues", []))
        if accuracy_score < settings.verifier_accuracy_threshold:
            VERIFIER_FAILURES.labels(check_type="accuracy").inc()

        # 3. Rule-based checks
        if len(generated) > 5000:
            issues.append("Ответ слишком длинный (>5000 символов)")
        if not chunks:
            issues.append("Ответ без источников")

        # Decision logic
        verification_passed = (
            not hallucination_detected
            and accuracy_score >= settings.verifier_accuracy_threshold
            and len(issues) <= 2
        )

        elapsed_s = time.perf_counter() - start
        elapsed = elapsed_s * 1000
        AGENT_NODE_DURATION.labels(node_name="verifier").observe(elapsed_s)

        span.set_attribute("verification_passed", verification_passed)
        span.set_attribute("accuracy_score", accuracy_score)
        span.set_attribute("hallucination_detected", hallucination_detected)
        span.set_attribute("issues_count", len(issues))

    logger.info(
        "verifier_completed",
        passed=verification_passed,
        accuracy=accuracy_score,
        hallucination=hallucination_detected,
        issues_count=len(issues),
    )

    return {
        "current_node": "verifier",
        "verification_passed": verification_passed,
        "hallucination_detected": hallucination_detected,
        "legal_accuracy_score": accuracy_score,
        "verification_issues": issues,
        "final_response": generated if verification_passed else None,
        "final_status": "COMPLETED" if verification_passed else "NEEDS_ACTION",
        "node_timings": {**state.get("node_timings", {}), "verifier": elapsed},
    }


# ── Escalation Node ────────────────────────────────────

async def escalation_node(state: PipelineState) -> dict[str, Any]:
    """Package context and create escalation record."""
    start = time.perf_counter()

    with tracer.start_as_current_span("escalation_node") as span:
        span.set_attribute("pipeline_run_id", state.get("pipeline_run_id", ""))
        span.set_attribute("risk_level", state.get("risk_level", ""))

        reason_parts = []
        if state.get("hallucination_detected"):
            reason_parts.append("Обнаружены галлюцинации")
        if (state.get("legal_accuracy_score") or 1.0) < 0.60:
            reason_parts.append(f"Низкая точность: {state.get('legal_accuracy_score')}")
        if state.get("risk_level") == "CRITICAL":
            reason_parts.append("Критический уровень риска")
        if (state.get("classifier_confidence") or 1.0) < 0.30:
            reason_parts.append(f"Низкая уверенность классификатора: {state.get('classifier_confidence')}")
        if state.get("human_decision") == "REJECTED":
            reason_parts.append("Отклонено рецензентом")

        reason = "; ".join(reason_parts) or "Требуется эскалация"
        case_id = str(uuid4())

        priority = RiskPolicyService.escalation_priority_from_risk(state.get("risk_level", "MEDIUM"))
        ESCALATIONS_TOTAL.labels(priority=priority).inc()
        span.set_attribute("escalation_reason", reason)

        elapsed_s = time.perf_counter() - start
        elapsed = elapsed_s * 1000
        AGENT_NODE_DURATION.labels(node_name="escalation").observe(elapsed_s)

    logger.info("escalation_node_completed", case_id=case_id, reason=reason)

    return {
        "current_node": "escalation",
        "escalation_required": True,
        "escalation_reason": reason,
        "escalation_case_id": case_id,
        "final_status": "ESCALATED",
        "node_timings": {**state.get("node_timings", {}), "escalation": elapsed},
    }


# ── Human Loop Node ────────────────────────────────────

async def human_loop_node(state: PipelineState) -> dict[str, Any]:
    """Create HITL task and pause for review. Graph will interrupt here."""
    start = time.perf_counter()

    with tracer.start_as_current_span("human_loop_node") as span:
        span.set_attribute("pipeline_run_id", state.get("pipeline_run_id", ""))
        span.set_attribute("risk_level", state.get("risk_level", ""))

        review_task_id = str(uuid4())
        risk = state.get("risk_level", "MEDIUM")
        priority = RiskPolicyService.review_priority_from_risk(risk)

        HITL_TASKS_CREATED.labels(priority=priority).inc()

        reason = state.get("human_review_reason") or f"Risk: {risk}, requires manual review"
        elapsed_s = time.perf_counter() - start
        elapsed = elapsed_s * 1000
        AGENT_NODE_DURATION.labels(node_name="human_loop").observe(elapsed_s)

        span.set_attribute("review_task_id", review_task_id)
        span.set_attribute("priority", priority)

    logger.info("human_loop_task_created", task_id=review_task_id, priority=priority)

    return {
        "current_node": "human_loop",
        "requires_human_review": True,
        "human_review_reason": reason,
        "human_review_task_id": review_task_id,
        "final_status": "AWAITING_REVIEW",
        "node_timings": {**state.get("node_timings", {}), "human_loop": elapsed},
    }
