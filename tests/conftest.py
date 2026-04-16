from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return settings pointing to test DB (uses env vars or defaults)."""
    return Settings(
        database_url=os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://legalops:legalops_secret@localhost:5433/legalops_test",
        ),
        redis_url=os.getenv("TEST_REDIS_URL", "redis://localhost:6380/1"),
        secret_key="test-secret-key-must-be-32b-long",
        paseto_key="test-paseto-key-must-be-32b-long",
        app_env="development",
        debug=True,
        log_level="WARNING",
    )


@pytest_asyncio.fixture(scope="session")
async def engine(test_settings: Settings):
    """Create engine for test DB."""
    eng = create_async_engine(
        test_settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=5,
    )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh transactional session for each test — auto-rollback."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with session_factory() as session:
            yield session
        await trans.rollback()


@pytest.fixture
def make_uuid():
    """Factory for deterministic UUIDs."""
    return lambda: uuid4()
