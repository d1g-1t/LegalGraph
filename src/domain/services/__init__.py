"""Domain services — business rules that span multiple entities."""

from __future__ import annotations

from src.domain.value_objects import EscalationPriority, ReviewPriority, RiskLevel


class RiskPolicyService:
    """Determine review / escalation priority from risk level."""

    @staticmethod
    def review_priority_from_risk(risk_level: str) -> str:
        """Map risk level to HITL review priority."""
        mapping: dict[str, str] = {
            RiskLevel.CRITICAL: ReviewPriority.URGENT,
            RiskLevel.HIGH: ReviewPriority.HIGH,
            RiskLevel.MEDIUM: ReviewPriority.NORMAL,
            RiskLevel.LOW: ReviewPriority.NORMAL,
        }
        return mapping.get(risk_level, ReviewPriority.NORMAL)

    @staticmethod
    def escalation_priority_from_risk(risk_level: str) -> str:
        """Map risk level to escalation priority."""
        mapping: dict[str, str] = {
            RiskLevel.CRITICAL: EscalationPriority.CRITICAL,
            RiskLevel.HIGH: EscalationPriority.HIGH,
            RiskLevel.MEDIUM: EscalationPriority.NORMAL,
            RiskLevel.LOW: EscalationPriority.LOW,
        }
        return mapping.get(risk_level, EscalationPriority.NORMAL)

    @staticmethod
    def needs_immediate_escalation(risk_level: str, confidence: float) -> bool:
        """Return True if request must skip to escalation."""
        return risk_level == RiskLevel.CRITICAL or confidence < 0.30

    @staticmethod
    def needs_human_review(risk_level: str, requires_human: bool) -> bool:
        """Return True if request should be routed to HITL."""
        return risk_level == RiskLevel.HIGH or requires_human
