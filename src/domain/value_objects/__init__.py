"""Domain value objects — enums and lightweight immutable types."""

from __future__ import annotations

from enum import StrEnum


class RequestCategory(StrEnum):
    """Legal request categories recognised by the classifier."""

    CONTRACT_REVIEW = "CONTRACT_REVIEW"
    CONTRACT_DRAFT = "CONTRACT_DRAFT"
    LEGAL_FAQ = "LEGAL_FAQ"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    COURT_PREPARATION = "COURT_PREPARATION"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    DATA_PRIVACY = "DATA_PRIVACY"
    OTHER = "OTHER"


class RiskLevel(StrEnum):
    """Risk classification produced by the classifier."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RequestChannel(StrEnum):
    """Channel through which a request arrived."""

    API = "API"
    WEB = "WEB"
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"


class RequestPriority(StrEnum):
    """Business priority of a legal request."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PipelineStatus(StrEnum):
    """Lifecycle status of a pipeline run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class StepStatus(StrEnum):
    """Status of a single agent step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class HumanDecision(StrEnum):
    """Reviewer's decision on a pending HITL task."""

    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"


class ReviewStatus(StrEnum):
    """Status of a human review task."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    DECIDED = "DECIDED"
    EXPIRED = "EXPIRED"


class ReviewPriority(StrEnum):
    """SLA-linked priority for human review."""

    URGENT = "URGENT"
    HIGH = "HIGH"
    NORMAL = "NORMAL"


class EscalationStatus(StrEnum):
    """Escalation case lifecycle."""

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class EscalationPriority(StrEnum):
    """Escalation urgency."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UserRole(StrEnum):
    """RBAC roles."""

    ADMIN = "ADMIN"
    LAWYER = "LAWYER"
    REVIEWER = "REVIEWER"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"
