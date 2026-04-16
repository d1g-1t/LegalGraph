from __future__ import annotations

import pytest

from src.domain.value_objects import (
    EscalationPriority,
    EscalationStatus,
    HumanDecision,
    PipelineStatus,
    RequestCategory,
    RequestChannel,
    RequestPriority,
    ReviewPriority,
    ReviewStatus,
    RiskLevel,
    StepStatus,
    UserRole,
)


class TestRequestCategory:

    def test_all_values(self):
        expected = {
            "CONTRACT_REVIEW", "CONTRACT_DRAFT", "LEGAL_FAQ",
            "COMPLIANCE_CHECK", "COURT_PREPARATION", "CORPORATE_ACTION",
            "DATA_PRIVACY", "OTHER",
        }
        assert {c.value for c in RequestCategory} == expected

    def test_string_coercion(self):
        assert str(RequestCategory.LEGAL_FAQ) == "LEGAL_FAQ"
        assert RequestCategory("CONTRACT_REVIEW") == RequestCategory.CONTRACT_REVIEW


class TestRiskLevel:

    def test_values(self):
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"


class TestPipelineStatus:

    def test_terminal_statuses(self):
        terminal = {PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.ESCALATED}
        for s in terminal:
            assert s in PipelineStatus

    def test_active_statuses(self):
        active = {PipelineStatus.PENDING, PipelineStatus.RUNNING, PipelineStatus.AWAITING_REVIEW}
        for s in active:
            assert s in PipelineStatus


class TestUserRole:

    def test_all_roles(self):
        expected = {"ADMIN", "LAWYER", "REVIEWER", "ANALYST", "VIEWER"}
        assert {r.value for r in UserRole} == expected


class TestHumanDecision:

    def test_values(self):
        assert HumanDecision.APPROVED.value == "APPROVED"
        assert HumanDecision.EDITED.value == "EDITED"
        assert HumanDecision.REJECTED.value == "REJECTED"


class TestReviewStatus:

    def test_flow(self):
        assert ReviewStatus.PENDING.value == "PENDING"
        assert ReviewStatus.IN_REVIEW.value == "IN_REVIEW"
        assert ReviewStatus.DECIDED.value == "DECIDED"
        assert ReviewStatus.EXPIRED.value == "EXPIRED"


class TestEscalationStatus:

    def test_values(self):
        statuses = {s.value for s in EscalationStatus}
        assert "OPEN" in statuses
        assert "ASSIGNED" in statuses
        assert "RESOLVED" in statuses
        assert "CLOSED" in statuses


class TestRequestChannel:

    def test_values(self):
        channels = {c.value for c in RequestChannel}
        assert {"API", "WEB", "EMAIL", "TELEGRAM"} == channels


class TestStepStatus:

    def test_values(self):
        assert StepStatus.PENDING.value == "PENDING"
        assert StepStatus.COMPLETED.value == "COMPLETED"
        assert StepStatus.FAILED.value == "FAILED"
        assert StepStatus.SKIPPED.value == "SKIPPED"
