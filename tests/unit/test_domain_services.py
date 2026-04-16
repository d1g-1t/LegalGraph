from __future__ import annotations

import pytest

from src.domain.services import RiskPolicyService
from src.domain.value_objects import RiskLevel


class TestRiskPolicyService:

    @pytest.mark.parametrize(
        "risk_level,confidence,expected_escalation",
        [
            ("CRITICAL", 0.9, True),
            ("CRITICAL", 0.1, True),
            ("HIGH", 0.5, False),
            ("MEDIUM", 0.5, False),
            ("LOW", 0.5, False),
            ("HIGH", 0.2, False),
            ("LOW", 0.1, False),
        ],
    )
    def test_needs_immediate_escalation(self, risk_level, confidence, expected_escalation):
        result = RiskPolicyService.needs_immediate_escalation(risk_level, confidence)
        assert result is expected_escalation

    @pytest.mark.parametrize(
        "risk_level,requires_human,expected_hitl",
        [
            ("LOW", False, False),
            ("LOW", True, True),
            ("MEDIUM", False, False),
            ("HIGH", False, True),
            ("HIGH", True, True),
            ("CRITICAL", False, True),
        ],
    )
    def test_needs_human_review(self, risk_level, requires_human, expected_hitl):
        result = RiskPolicyService.needs_human_review(risk_level, requires_human)
        assert result is expected_hitl

    @pytest.mark.parametrize(
        "risk_level,expected_priority",
        [
            ("LOW", "NORMAL"),
            ("MEDIUM", "NORMAL"),
            ("HIGH", "HIGH"),
            ("CRITICAL", "URGENT"),
        ],
    )
    def test_review_priority_from_risk(self, risk_level, expected_priority):
        result = RiskPolicyService.review_priority_from_risk(risk_level)
        assert result == expected_priority

    @pytest.mark.parametrize(
        "risk_level,expected_priority",
        [
            ("LOW", "LOW"),
            ("MEDIUM", "NORMAL"),
            ("HIGH", "HIGH"),
            ("CRITICAL", "CRITICAL"),
        ],
    )
    def test_escalation_priority_from_risk(self, risk_level, expected_priority):
        result = RiskPolicyService.escalation_priority_from_risk(risk_level)
        assert result == expected_priority
