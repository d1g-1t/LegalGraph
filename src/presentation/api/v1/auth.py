from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dto import LoginRequest, RefreshRequest, TokenResponse, UserOut
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.domain.entities import ApiUser
from src.infrastructure.database.repositories import UserRepository
from src.presentation.deps import get_current_user, get_db_session

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Authenticate user")
async def login(body: LoginRequest, session=Depends(get_db_session)) -> TokenResponse:
    repo = UserRepository(session)
    user = await repo.get_by_email(body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учётные данные")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт деактивирован")

    access = create_access_token(user.id, user.role, user.legal_entity_id)
    refresh, _jti = create_refresh_token(user.id, user.role)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse, summary="Refresh tokens")
async def refresh(body: RefreshRequest, session=Depends(get_db_session)) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    user_id = UUID(payload["sub"])
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access = create_access_token(user.id, user.role, user.legal_entity_id)
    new_refresh, _jti = create_refresh_token(user.id, user.role)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserOut, summary="Current user info")
async def me(user: ApiUser = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, role=user.role,
        legal_entity_id=user.legal_entity_id,
        is_active=user.is_active, created_at=user.created_at,
    )
