"""Prometheus metrics — counters, histograms, gauges for the pipeline."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# ── Application info ──────────────────────────────────────────────────────
APP_INFO = Info("legalops", "LegalOpsAI-Pipeline application metadata")
APP_INFO.info({"version": "0.1.0", "service": "legalops-ai-pipeline"})

# ── HTTP Request metrics ──────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL = Counter(
    "legalops_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION = Histogram(
    "legalops_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Pipeline metrics ──────────────────────────────────────────────────────
PIPELINE_RUNS_TOTAL = Counter(
    "legalops_pipeline_runs_total",
    "Total pipeline runs started",
    ["category"],
)
PIPELINE_RUNS_COMPLETED = Counter(
    "legalops_pipeline_runs_completed_total",
    "Total pipeline runs completed",
    ["category", "status"],
)
PIPELINE_DURATION = Histogram(
    "legalops_pipeline_duration_seconds",
    "End-to-end pipeline execution time",
    ["category"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)
PIPELINE_ACTIVE = Gauge(
    "legalops_pipeline_active_runs",
    "Currently active pipeline runs",
)

# ── Agent node metrics ────────────────────────────────────────────────────
AGENT_NODE_DURATION = Histogram(
    "legalops_agent_node_duration_seconds",
    "Agent node execution time",
    ["node_name"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
AGENT_NODE_ERRORS = Counter(
    "legalops_agent_node_errors_total",
    "Agent node errors",
    ["node_name", "error_type"],
)

# ── LLM metrics ───────────────────────────────────────────────────────────
LLM_REQUESTS_TOTAL = Counter(
    "legalops_llm_requests_total",
    "Total LLM inference requests",
    ["model", "node_name"],
)
LLM_TOKENS_TOTAL = Counter(
    "legalops_llm_tokens_total",
    "Total tokens consumed",
    ["model", "token_type"],  # token_type: prompt / completion
)
LLM_LATENCY = Histogram(
    "legalops_llm_latency_seconds",
    "LLM request latency",
    ["model"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
)

# ── RAG / Retrieval metrics ──────────────────────────────────────────────
RAG_SEARCHES_TOTAL = Counter(
    "legalops_rag_searches_total",
    "Total RAG search requests",
)
RAG_CHUNKS_RETRIEVED = Histogram(
    "legalops_rag_chunks_retrieved",
    "Number of chunks retrieved per search",
    buckets=(1, 3, 5, 10, 15, 20, 30),
)
RAG_SEARCH_LATENCY = Histogram(
    "legalops_rag_search_latency_seconds",
    "RAG search latency",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# ── HITL metrics ──────────────────────────────────────────────────────────
HITL_TASKS_CREATED = Counter(
    "legalops_hitl_tasks_created_total",
    "Human review tasks created",
    ["priority"],
)
HITL_DECISIONS_TOTAL = Counter(
    "legalops_hitl_decisions_total",
    "Human review decisions made",
    ["decision"],  # approve / reject / edit
)
HITL_PENDING_TASKS = Gauge(
    "legalops_hitl_pending_tasks",
    "Currently pending HITL tasks",
)
HITL_SLA_BREACHES = Counter(
    "legalops_hitl_sla_breaches_total",
    "Number of SLA breaches for HITL tasks",
)

# ── Escalation metrics ────────────────────────────────────────────────────
ESCALATIONS_TOTAL = Counter(
    "legalops_escalations_total",
    "Total escalation cases created",
    ["priority"],
)
ESCALATIONS_ACTIVE = Gauge(
    "legalops_escalations_active",
    "Currently active (unresolved) escalation cases",
)

# ── Knowledge Base metrics ────────────────────────────────────────────────
KB_DOCUMENTS_INGESTED = Counter(
    "legalops_kb_documents_ingested_total",
    "Total documents ingested into KB",
)
KB_CHUNKS_TOTAL = Gauge(
    "legalops_kb_chunks_total",
    "Total number of chunks in the knowledge base",
)
KB_INGESTION_DURATION = Histogram(
    "legalops_kb_ingestion_duration_seconds",
    "Document ingestion time",
    buckets=(1, 5, 10, 30, 60, 120, 300),
)

# ── Verifier metrics ──────────────────────────────────────────────────────
VERIFIER_CHECKS_TOTAL = Counter(
    "legalops_verifier_checks_total",
    "Total verifier checks executed",
    ["check_type"],  # hallucination / accuracy
)
VERIFIER_FAILURES = Counter(
    "legalops_verifier_failures_total",
    "Verifier check failures (below threshold)",
    ["check_type"],
)

# ── Classifier metrics ────────────────────────────────────────────────────
CLASSIFIER_PREDICTIONS = Counter(
    "legalops_classifier_predictions_total",
    "Classifier category predictions",
    ["category", "risk_level"],
)
