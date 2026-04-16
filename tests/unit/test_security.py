from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:

    def test_hash_and_verify(self):
        raw = "MyS3cur3P@ssw0rd!"
        hashed = hash_password(raw)
        assert hashed != raw
        assert verify_password(raw, hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestPasetoTokens:

    @pytest.fixture(autouse=True)
    def _patch_settings(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-must-be-32b-long")
        monkeypatch.setenv("PASETO_KEY", "test-paseto-key-must-be-32b-long")

    def test_create_and_decode_access(self):
        user_id = uuid4()
        token = create_access_token(
            user_id=user_id,
            role="ADMIN",
        )
        assert isinstance(token, str)
        assert len(token) > 50

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "ADMIN"
        assert payload["typ"] == "access"

    def test_create_and_decode_refresh(self):
        user_id = uuid4()
        token, jti = create_refresh_token(user_id=user_id, role="VIEWER")
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert len(jti) == 32

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["typ"] == "refresh"
        assert payload["jti"] == jti

    def test_expired_token(self):
        user_id = uuid4()
        token = create_access_token(
            user_id=user_id,
            role="VIEWER",
            expires_minutes=-1,
        )
        with pytest.raises(ValueError, match="expired"):
            decode_token(token)

    def test_legal_entity_in_token(self):
        user_id = uuid4()
        entity_id = uuid4()
        token = create_access_token(
            user_id=user_id,
            role="LAWYER",
            legal_entity_id=entity_id,
        )
        payload = decode_token(token)
        assert payload["legal_entity_id"] == str(entity_id)
