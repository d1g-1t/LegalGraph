"""Domain repository interfaces — ports in hexagonal architecture.

Infrastructure layer provides concrete adapters implementing these protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence
from uuid import UUID

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


class IUserRepository(ABC):
    """Port: user persistence."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> ApiUser | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> ApiUser | None: ...

    @abstractmethod
    async def create(self, user: ApiUser) -> ApiUser: ...

    @abstractmethod
    async def list_by_role(self, role: str, limit: int = 50, offset: int = 0) -> Sequence[ApiUser]: ...


class ILegalRequestRepository(ABC):
    """Port: legal request persistence."""

    @abstractmethod
    async def create(self, request: LegalRequest) -> LegalRequest: ...

    @abstractmethod
    async def get_by_id(self, request_id: UUID) -> LegalRequest | None: ...

    @abstractmethod
    async def list_requests(
        self,
        *,
        legal_entity_id: UUID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[LegalRequest]: ...

    @abstractmethod
    async def update_status(self, request_id: UUID, status: str) -> None: ...


class IPipelineRunRepository(ABC):
    """Port: pipeline run persistence."""

    @abstractmethod
    async def create(self, run: PipelineRun) -> PipelineRun: ...

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> PipelineRun | None: ...

    @abstractmethod
    async def get_by_thread_id(self, thread_id: str) -> PipelineRun | None: ...

    @abstractmethod
    async def update(self, run: PipelineRun) -> None: ...

    @abstractmethod
    async def count_active(self) -> int: ...


class IAgentStepRepository(ABC):
    """Port: agent step persistence."""

    @abstractmethod
    async def create(self, step: AgentStep) -> AgentStep: ...

    @abstractmethod
    async def list_by_pipeline(self, pipeline_run_id: UUID) -> Sequence[AgentStep]: ...


class IKnowledgeDocumentRepository(ABC):
    """Port: knowledge document persistence."""

    @abstractmethod
    async def create(self, doc: KnowledgeDocument) -> KnowledgeDocument: ...

    @abstractmethod
    async def get_by_id(self, doc_id: UUID) -> KnowledgeDocument | None: ...

    @abstractmethod
    async def list_documents(self, limit: int = 50, offset: int = 0) -> Sequence[KnowledgeDocument]: ...

    @abstractmethod
    async def delete(self, doc_id: UUID) -> None: ...

    @abstractmethod
    async def update_chunk_count(self, doc_id: UUID, count: int) -> None: ...

    @abstractmethod
    async def count_total(self) -> int: ...


class IKnowledgeChunkRepository(ABC):
    """Port: knowledge chunk persistence & vector search."""

    @abstractmethod
    async def bulk_create(self, chunks: Sequence[KnowledgeChunk]) -> int: ...

    @abstractmethod
    async def semantic_search(
        self,
        embedding: list[float],
        *,
        legal_entity_id: UUID | None = None,
        category: str | None = None,
        top_k: int = 8,
    ) -> Sequence[RetrievedChunk]: ...

    @abstractmethod
    async def fulltext_search(
        self,
        query: str,
        *,
        legal_entity_id: UUID | None = None,
        top_k: int = 8,
    ) -> Sequence[RetrievedChunk]: ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> int: ...

    @abstractmethod
    async def exists_by_hash(self, content_hash: str) -> bool: ...

    @abstractmethod
    async def count_total(self) -> int: ...


class IHumanReviewRepository(ABC):
    """Port: HITL task persistence."""

    @abstractmethod
    async def create(self, task: HumanReviewTask) -> HumanReviewTask: ...

    @abstractmethod
    async def get_by_pipeline(self, pipeline_run_id: UUID) -> HumanReviewTask | None: ...

    @abstractmethod
    async def list_pending(self, limit: int = 20, offset: int = 0) -> Sequence[HumanReviewTask]: ...

    @abstractmethod
    async def update(self, task: HumanReviewTask) -> None: ...

    @abstractmethod
    async def count_pending(self) -> int: ...

    @abstractmethod
    async def list_overdue(self, now: datetime) -> Sequence[HumanReviewTask]: ...

    @abstractmethod
    async def get_next_reviewer_id(self, role: str) -> UUID | None: ...


class IEscalationRepository(ABC):
    """Port: escalation case persistence."""

    @abstractmethod
    async def create(self, case: EscalationCase) -> EscalationCase: ...

    @abstractmethod
    async def get_by_id(self, case_id: UUID) -> EscalationCase | None: ...

    @abstractmethod
    async def list_cases(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[EscalationCase]: ...

    @abstractmethod
    async def update(self, case: EscalationCase) -> None: ...
