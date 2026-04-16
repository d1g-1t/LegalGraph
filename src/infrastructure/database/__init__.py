"""Database package — async engine, session factory, base model."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def build_engine(url: str | None = None):
    """Create an async SQLAlchemy engine."""
    settings = get_settings()
    db_url = url or settings.database_url
    return create_async_engine(
        db_url,
        echo=settings.debug,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def build_session_factory(engine=None) -> async_sessionmaker[AsyncSession]:
    """Build an async session factory."""
    if engine is None:
        engine = build_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
