from __future__ import annotations

from typing import Annotated, Sequence
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from src.core.security import decode_token
from src.domain.entities import ApiUser
from src.domain.value_objects import UserRole
from src.infrastructure.database import build_session_factory
from src.infrastructure.database.repositories import UserRepository

_session_factory = None


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = build_session_factory()
    return _session_factory


async def get_db_session():
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session=Depends(get_db_session),
) -> ApiUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_roles(*roles: str):

    async def _check(user: ApiUser = Depends(get_current_user)) -> ApiUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not permitted. Required: {roles}",
            )
        return user

    return _check
