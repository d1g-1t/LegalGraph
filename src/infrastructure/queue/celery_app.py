from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "legalops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "src.infrastructure.queue.tasks.run_pipeline_task": {"queue": "legalops.pipeline"},
        "src.infrastructure.queue.tasks.ingest_knowledge_document_task": {"queue": "legalops.ingest"},
        "src.infrastructure.queue.tasks.hitl_sla_monitor_task": {"queue": "legalops.monitoring"},
        "src.infrastructure.queue.tasks.analytics_refresh_task": {"queue": "legalops.analytics"},
        "src.infrastructure.queue.tasks.cleanup_terminal_pipeline_artifacts_task": {"queue": "legalops.monitoring"},
    },
    beat_schedule={
        "hitl-sla-monitor": {
            "task": "src.infrastructure.queue.tasks.hitl_sla_monitor_task",
            "schedule": crontab(minute="*/5"),
        },
        "analytics-refresh": {
            "task": "src.infrastructure.queue.tasks.analytics_refresh_task",
            "schedule": crontab(minute="*/15"),
        },
        "cleanup-stale-artifacts": {
            "task": "src.infrastructure.queue.tasks.cleanup_terminal_pipeline_artifacts_task",
            "schedule": crontab(hour="3", minute="0"),
        },
    },
)
