"""Initial schema — all tables, extensions, indexes.

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create extensions and all tables."""
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # api_users
    op.create_table(
        "api_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="VIEWER"),
        sa.Column("legal_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_users_email", "api_users", ["email"])

    # legal_requests
    op.create_table(
        "legal_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("api_users.id"), nullable=False),
        sa.Column("legal_entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False, server_default="API"),
        sa.Column("priority", sa.String(32), nullable=False, server_default="NORMAL"),
        sa.Column("raw_input", sa.Text, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_legal_requests_status", "legal_requests", ["status"])

    # pipeline_runs
    op.create_table(
        "pipeline_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", UUID(as_uuid=True), sa.ForeignKey("legal_requests.id"), nullable=False),
        sa.Column("thread_id", sa.String(128), unique=True, nullable=False),
        sa.Column("pipeline_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("intent", sa.Text, nullable=True),
        sa.Column("risk_level", sa.String(32), nullable=True),
        sa.Column("classifier_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("generated_response", sa.Text, nullable=True),
        sa.Column("final_response", sa.Text, nullable=True),
        sa.Column("verification_passed", sa.Boolean, nullable=True),
        sa.Column("legal_accuracy_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("hallucination_detected", sa.Boolean, nullable=True),
        sa.Column("requires_human_review", sa.Boolean, server_default=sa.text("false")),
        sa.Column("human_decision", sa.String(32), nullable=True),
        sa.Column("escalation_case_id", UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("node_timings", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["pipeline_status"])
    op.create_index("ix_pipeline_runs_risk", "pipeline_runs", ["risk_level"])

    # agent_steps
    op.create_table(
        "agent_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("node_name", sa.String(64), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("input_snapshot", JSONB, nullable=True),
        sa.Column("output_snapshot", JSONB, nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("otel_span_id", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_steps_run", "agent_steps", ["pipeline_run_id"])

    # knowledge_documents
    op.create_table(
        "knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_global", sa.Boolean, server_default=sa.text("false")),
        sa.Column("document_name", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("total_chunks", sa.Integer, server_default=sa.text("0")),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # knowledge_chunks
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("legal_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_global", sa.Boolean, server_default=sa.text("false")),
        sa.Column("document_name", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("total_chunks", sa.Integer, nullable=False),
        sa.Column("section_header", sa.String(512), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # pgvector column added via raw SQL
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding vector(768)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_content_fts "
        "ON knowledge_chunks USING gin (to_tsvector('russian', content))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_metadata_gin ON knowledge_chunks USING gin (metadata)")
    op.create_index("ix_chunks_document", "knowledge_chunks", ["document_id"])

    # human_review_tasks
    op.create_table(
        "human_review_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("assigned_reviewer_id", UUID(as_uuid=True), sa.ForeignKey("api_users.id"), nullable=True),
        sa.Column("priority", sa.String(32), nullable=False, server_default="NORMAL"),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(32), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("edited_response", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_status", "human_review_tasks", ["status"])
    op.create_index("ix_review_deadline", "human_review_tasks", ["deadline_at"])

    # escalation_cases
    op.create_table(
        "escalation_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False, server_default="NORMAL"),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("assigned_lawyer_id", UUID(as_uuid=True), sa.ForeignKey("api_users.id"), nullable=True),
        sa.Column("context_package", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_escalation_status", "escalation_cases", ["status"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("escalation_cases")
    op.drop_table("human_review_tasks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("agent_steps")
    op.drop_table("pipeline_runs")
    op.drop_table("legal_requests")
    op.drop_table("api_users")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
