from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.infrastructure.queue.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name="src.infrastructure.queue.tasks.run_pipeline_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_pipeline_task(self, pipeline_run_id: str) -> dict:
    logger.info("pipeline_task_started", pipeline_run_id=pipeline_run_id)
    start = time.perf_counter()

    async def _execute():
        from src.infrastructure.database import build_session_factory
        from src.infrastructure.database.repositories import (
            LegalRequestRepository,
            PipelineRunRepository,
        )
        from src.infrastructure.agents.graph import compile_pipeline

        session_factory = build_session_factory()
        async with session_factory() as session:
            run_repo = PipelineRunRepository(session)
            run_id = UUID(pipeline_run_id)
            run = await run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Pipeline run not found: {pipeline_run_id}")

            req_repo = LegalRequestRepository(session)
            request = await req_repo.get_by_id(run.request_id)
            if not request:
                raise ValueError(f"Request not found: {run.request_id}")

            initial_state = {
                "request_id": str(request.id),
                "pipeline_run_id": str(run.id),
                "requester_id": str(request.requester_id),
                "legal_entity_id": str(request.legal_entity_id),
                "raw_input": request.raw_input,
                "submitted_at": request.submitted_at.isoformat(),
                "current_node": "start",
                "generation_retry_count": 0,
                "requires_human_review": False,
                "escalation_required": False,
                "errors": [],
                "node_timings": {},
                "retrieved_chunks": [],
                "extracted_entities": [],
                "verification_issues": [],
            }

            run.pipeline_status = "RUNNING"
            await run_repo.update(run)
            await session.commit()

            graph = compile_pipeline()
            config = {"configurable": {"thread_id": str(run.id)}}

            try:
                final_state = await graph.ainvoke(initial_state, config=config)
            except Exception as exc:
                run.pipeline_status = "FAILED"
                run.error_message = str(exc)[:500]
                run.completed_at = datetime.now(UTC)
                await run_repo.update(run)
                await session.commit()
                raise

            run.pipeline_status = final_state.get("final_status", "COMPLETED")
            run.category = final_state.get("category")
            run.intent = final_state.get("intent")
            run.risk_level = final_state.get("risk_level")
            run.classifier_confidence = final_state.get("classifier_confidence")
            run.generated_response = final_state.get("generated_response")
            run.final_response = final_state.get("final_response")
            run.verification_passed = final_state.get("verification_passed")
            run.legal_accuracy_score = final_state.get("legal_accuracy_score")
            run.hallucination_detected = final_state.get("hallucination_detected")
            run.requires_human_review = final_state.get("requires_human_review", False)
            run.node_timings = final_state.get("node_timings", {})
            run.trace_id = final_state.get("trace_id")
            elapsed = (time.perf_counter() - start) * 1000
            run.total_duration_ms = int(elapsed)
            run.completed_at = datetime.now(UTC)
            await run_repo.update(run)

            await req_repo.update_status(request.id, run.pipeline_status)
            await session.commit()

            return {
                "pipeline_run_id": pipeline_run_id,
                "status": run.pipeline_status,
                "duration_ms": int(elapsed),
            }

    try:
        result = _run_async(_execute())
        logger.info("pipeline_task_completed", **result)
        return result
    except Exception as exc:
        logger.error("pipeline_task_failed", error=str(exc), pipeline_run_id=pipeline_run_id)
        raise self.retry(exc=exc)


@celery_app.task(
    name="src.infrastructure.queue.tasks.ingest_knowledge_document_task",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def ingest_knowledge_document_task(self, document_id: str, file_path: str) -> dict:
    logger.info("ingest_task_started", document_id=document_id)

    async def _execute():
        from src.infrastructure.database import build_session_factory
        from src.infrastructure.database.repositories import (
            KnowledgeChunkRepository,
            KnowledgeDocumentRepository,
        )
        from src.infrastructure.llm import OllamaLLMService
        from src.infrastructure.rag import RAGService

        session_factory = build_session_factory()
        async with session_factory() as session:
            doc_repo = KnowledgeDocumentRepository(session)
            chunk_repo = KnowledgeChunkRepository(session)
            llm = OllamaLLMService()
            rag = RAGService(doc_repo, chunk_repo, llm)

            doc = await doc_repo.get_by_id(UUID(document_id))
            if not doc:
                raise ValueError(f"Document not found: {document_id}")

            count = await rag.ingest_document(doc, file_path)
            await session.commit()
            return {"document_id": document_id, "chunks": count}

    try:
        result = _run_async(_execute())
        logger.info("ingest_task_completed", **result)
        return result
    except Exception as exc:
        logger.error("ingest_task_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="src.infrastructure.queue.tasks.hitl_sla_monitor_task")
def hitl_sla_monitor_task() -> dict:
    logger.info("hitl_sla_monitor_started")

    async def _execute():
        from src.infrastructure.database import build_session_factory
        from src.infrastructure.database.repositories import HumanReviewRepository

        session_factory = build_session_factory()
        async with session_factory() as session:
            repo = HumanReviewRepository(session)
            now = datetime.now(UTC)
            overdue = await repo.list_overdue(now)
            return {"overdue_count": len(overdue)}

    result = _run_async(_execute())
    logger.info("hitl_sla_monitor_completed", **result)
    return result


@celery_app.task(name="src.infrastructure.queue.tasks.analytics_refresh_task")
def analytics_refresh_task() -> dict:
    logger.info("analytics_refresh_started")
    return {"status": "refreshed"}


@celery_app.task(name="src.infrastructure.queue.tasks.cleanup_terminal_pipeline_artifacts_task")
def cleanup_terminal_pipeline_artifacts_task() -> dict:
    logger.info("cleanup_task_started")
    return {"status": "cleaned"}
