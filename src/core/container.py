from __future__ import annotations

from dependency_injector import containers, providers

from src.core.config import get_settings


class Container(containers.DeclarativeContainer):

    wiring_config = containers.WiringConfiguration(
        packages=["src.presentation", "src.application", "src.infrastructure"],
    )

    config = providers.Singleton(get_settings)

    db_session_factory = providers.Singleton(
        providers.Callable(
            lambda: __import__(
                "src.infrastructure.database", fromlist=["build_session_factory"]
            ).build_session_factory()
        ),
    )

    redis_client = providers.Singleton(
        providers.Callable(
            lambda: __import__("redis.asyncio", fromlist=["from_url"]).from_url(
                get_settings().redis_url, decode_responses=True
            )
        ),
    )

    llm_service = providers.Factory(
        providers.Callable(
            lambda: __import__(
                "src.infrastructure.llm", fromlist=["OllamaLLMService"]
            ).OllamaLLMService()
        ),
    )
