"""Agent policies — configurable routing rules."""

from __future__ import annotations

from src.core.config import get_settings


def should_escalate_immediately(risk_level: str, confidence: float) -> bool:
    """Return True if request must bypass normal flow."""
    settings = get_settings()
    return risk_level == "CRITICAL" or confidence < settings.classifier_confidence_threshold


def should_route_to_human(risk_level: str, requires_human: bool) -> bool:
    """Return True if HITL is required."""
    return risk_level == "HIGH" or requires_human


def should_retry_generation(accuracy: float, retry_count: int) -> bool:
    """Return True if generator should retry."""
    settings = get_settings()
    return accuracy < settings.verifier_accuracy_threshold and retry_count < settings.max_generation_retries
