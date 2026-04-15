from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.core.config import get_settings


def setup_telemetry() -> TracerProvider | None:
    """Initialise OTEL tracing and auto-instrumentation."""
    settings = get_settings()
    if not settings.otel_enabled:
        return None

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()

    return provider


def instrument_fastapi(app: object) -> None:
    """Instrument FastAPI app (must call after app creation)."""
    FastAPIInstrumentor.instrument_app(app)


def instrument_sqlalchemy(engine: object) -> None:
    """Instrument SQLAlchemy engine."""
    SQLAlchemyInstrumentor().instrument(engine=engine)


def get_tracer(name: str = "legalops") -> trace.Tracer:
    """Return an OTEL tracer scoped to *name*."""
    return trace.get_tracer(name)
