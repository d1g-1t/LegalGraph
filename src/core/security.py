from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pyseto
from passlib.context import CryptContext
from pydantic import BaseModel

from src.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):

    sub: str
    role: str
    legal_entity_id: str | None = None
    exp: float
    jti: str
    typ: str = "access"


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def _get_key() -> pyseto.KeyInterface:
    settings = get_settings()
    raw = settings.paseto_key.encode()[:32].ljust(32, b"\x00")
    return pyseto.Key.new(version=4, purpose="local", key=raw)


def create_access_token(
    user_id: UUID,
    role: str,
    legal_entity_id: UUID | None = None,
    expires_minutes: int = 60,
) -> str:
    """Create a PASETO v4.local access token."""
    now = datetime.now(UTC)
    payload = TokenPayload(
        sub=str(user_id),
        role=role,
        legal_entity_id=str(legal_entity_id) if legal_entity_id else None,
        exp=(now + timedelta(minutes=expires_minutes)).timestamp(),
        jti=secrets.token_hex(16),
        typ="access",
    )
    key = _get_key()
    token = pyseto.encode(key, payload.model_dump_json().encode())
    return token.decode() if isinstance(token, bytes) else str(token)


def create_refresh_token(
    user_id: UUID,
    role: str,
    expires_days: int = 30,
) -> tuple[str, str]:
    """Create a refresh token. Returns (token_str, jti)."""
    now = datetime.now(UTC)
    jti = secrets.token_hex(16)
    payload = TokenPayload(
        sub=str(user_id),
        role=role,
        exp=(now + timedelta(days=expires_days)).timestamp(),
        jti=jti,
        typ="refresh",
    )
    key = _get_key()
    token = pyseto.encode(key, payload.model_dump_json().encode())
    return (token.decode() if isinstance(token, bytes) else str(token)), jti


def decode_token(token_str: str) -> dict[str, Any]:
    """Decode and verify a PASETO token. Raises on failure."""
    key = _get_key()
    decoded = pyseto.decode(key, token_str)
    import json

    payload: dict[str, Any] = json.loads(decoded.payload)
    now_ts = datetime.now(UTC).timestamp()
    if payload.get("exp", 0) < now_ts:
        raise ValueError("Token expired")
    return payload
