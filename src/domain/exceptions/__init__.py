"""Domain exceptions — typed hierarchy for business errors."""

from __future__ import annotations

from uuid import UUID


class DomainError(Exception):
    """Base for all domain errors."""


class EntityNotFoundError(DomainError):
    """Raised when a domain entity lookup fails."""

    def __init__(self, entity_type: str, entity_id: UUID | str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} not found: {entity_id}")


class AuthenticationError(DomainError):
    """Bad credentials or expired token."""


class AuthorizationError(DomainError):
    """User lacks required permission."""

    def __init__(self, action: str, role: str) -> None:
        self.action = action
        self.role = role
        super().__init__(f"Role '{role}' cannot perform '{action}'")


class PipelineError(DomainError):
    """Any pipeline-execution failure."""


class ClassifierError(PipelineError):
    """Classifier node failed."""


class RetrieverError(PipelineError):
    """Retriever node failed."""


class GeneratorError(PipelineError):
    """Generator node failed."""


class VerifierError(PipelineError):
    """Verifier node failed."""


class EscalationError(DomainError):
    """Escalation-related failure."""


class HumanReviewError(DomainError):
    """HITL subsystem failure."""


class KnowledgeBaseError(DomainError):
    """RAG ingestion or search failure."""


class DuplicateEntityError(DomainError):
    """Attempt to insert a duplicate entity."""

    def __init__(self, entity_type: str, key: str) -> None:
        super().__init__(f"Duplicate {entity_type}: {key}")


class ValidationError(DomainError):
    """Business-rule validation failure."""
