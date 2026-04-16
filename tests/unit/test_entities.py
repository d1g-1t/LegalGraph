from __future__ import annotations

from uuid import uuid4

import pytest

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
from src.domain.value_objects import (
    PipelineStatus,
    RequestCategory,
    RequestPriority,
    RiskLevel,
    StepStatus,
    UserRole,
)


class TestLegalRequest:

    def test_create_default(self):
        req = LegalRequest(
            requester_id=uuid4(),
            legal_entity_id=uuid4(),
            raw_input="Как расторгнуть договор?",
        )
        assert req.channel == "API"
        assert req.priority == "NORMAL"
        assert req.id is not None
        assert req.status == "NEW"

    def test_fields_populated(self):
        uid = uuid4()
        lid = uuid4()
        req = LegalRequest(
            requester_id=uid,
            legal_entity_id=lid,
            raw_input="Вопрос по 152-ФЗ",
            channel="WEB",
            priority="URGENT",
        )
        assert req.requester_id == uid
        assert req.legal_entity_id == lid
        assert req.channel == "WEB"


class TestPipelineRun:

    def test_create(self):
        rid = uuid4()
        run = PipelineRun(request_id=rid)
        assert run.request_id == rid
        assert run.pipeline_status == "PENDING"

    def test_status_update(self):
        run = PipelineRun(request_id=uuid4())
        run.pipeline_status = PipelineStatus.RUNNING
        assert run.pipeline_status == PipelineStatus.RUNNING


class TestAgentStep:

    def test_create(self):
        step = AgentStep(
            pipeline_run_id=uuid4(),
            node_name="classifier",
            status=StepStatus.RUNNING,
        )
        assert step.node_name == "classifier"
        assert step.status == StepStatus.RUNNING


class TestKnowledgeDocument:

    def test_create(self):
        doc = KnowledgeDocument(
            document_name="contract.pdf",
            document_type="PDF",
            source_path="/tmp/contract.pdf",
            checksum="abc123",
        )
        assert doc.document_name == "contract.pdf"
        assert doc.document_type == "PDF"
        assert doc.total_chunks == 0
        assert doc.is_global is False


class TestRetrievedChunk:

    def test_score(self):
        chunk = RetrievedChunk(
            chunk_id=uuid4(),
            document_name="contract.pdf",
            content="Статья 1. Предмет договора.",
            score=0.92,
        )
        assert chunk.score == 0.92


class TestApiUser:

    def test_create(self):
        user = ApiUser(
            id=uuid4(),
            email="admin@legal.ru",
            hashed_password="x",
            role=UserRole.ADMIN,
        )
        assert user.role == UserRole.ADMIN
        assert user.is_active is True

    def test_viewer_role(self):
        user = ApiUser(
            email="viewer@legal.ru",
            hashed_password="x",
            role=UserRole.VIEWER,
        )
        user = ApiUser(
            email="viewer@legal.ru",
            hashed_password="x",
            role=UserRole.VIEWER,
        )
        assert user.role == UserRole.VIEWER


class TestHumanReviewTask:

    def test_defaults(self):
        task = HumanReviewTask(pipeline_run_id=uuid4(), reason="High risk contract")
        assert task.status == "PENDING"
        assert task.priority == "NORMAL"
        assert task.decision is None


class TestEscalationCase:

    def test_defaults(self):
        case = EscalationCase(
            pipeline_run_id=uuid4(),
            category="LITIGATION",
            risk_level="CRITICAL",
            reason="Иск на 15 млн ₽",
        )
        assert case.status == "OPEN"
        assert case.resolved_at is None
