from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LegalOpsAI-Pipeline"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    secret_key: str = Field(min_length=16)
    paseto_key: str = Field(min_length=16)

    api_host: str = "0.0.0.0"
    api_port: int = 8079
    api_workers: int = 1
    cors_origins: list[str] = ["http://localhost:3001"]

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "legalops"
    postgres_password: str = "legalops_secret"
    postgres_db: str = "legalops_db"
    database_url: str = "postgresql+asyncpg://legalops:legalops_secret@localhost:5433/legalops_db"

    redis_host: str = "localhost"
    redis_port: int = 6380
    redis_url: str = "redis://localhost:6380/0"

    celery_broker_url: str = "redis://localhost:6380/1"
    celery_result_backend: str = "redis://localhost:6380/2"

    ollama_base_url: str = "http://localhost:11435"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: int = 120

    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"
    langfuse_host: str = "http://localhost:3002"

    otel_service_name: str = "legalops-ai-pipeline"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_enabled: bool = True

    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 8
    rag_rerank_top_n: int = 5
    rag_similarity_threshold: float = 0.35
    rag_hybrid_search: bool = True
    embedding_batch_size: int = 32
    embedding_dimension: int = 768

    classifier_confidence_threshold: float = 0.30
    verifier_accuracy_threshold: float = 0.60
    max_generation_retries: int = 2

    hitl_sla_urgent_hours: int = 2
    hitl_sla_high_hours: int = 4
    hitl_sla_normal_hours: int = 8

    rate_limit_login: str = "10/minute"
    rate_limit_search: str = "30/minute"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def project_root(self) -> Path:
        """Return project root path."""
        return Path(__file__).resolve().parent.parent.parent

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton accessor for application settings."""
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
    return _settings
