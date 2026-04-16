from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.dto import (
    LoginRequest,
    ReviewDecisionIn,
    SearchRequest,
    SubmitRequestIn,
    TokenResponse,
)


class TestLoginRequest:

    def test_valid(self):
        dto = LoginRequest(email="admin@legal.ru", password="Str0ngP@ss!")
        assert dto.email == "admin@legal.ru"

    def test_invalid_email(self):
        with pytest.raises(Exception):
            LoginRequest(email="not-an-email", password="test123")

    def test_short_password(self):
        with pytest.raises(Exception):
            LoginRequest(email="a@b.com", password="12345")


class TestSubmitRequestIn:

    def test_valid_minimal(self):
        dto = SubmitRequestIn(raw_input="Вопрос по НДС для ООО Ромашка")
        assert dto.raw_input == "Вопрос по НДС для ООО Ромашка"
        assert dto.channel == "API"
        assert dto.priority == "NORMAL"

    def test_with_priority(self):
        dto = SubmitRequestIn(raw_input="Срочный юридический вопрос", priority="URGENT")
        assert dto.priority == "URGENT"

    def test_too_short(self):
        with pytest.raises(Exception):
            SubmitRequestIn(raw_input="123")


class TestReviewDecisionIn:

    def test_approved(self):
        dto = ReviewDecisionIn(decision="APPROVED", comment="Всё корректно")
        assert dto.decision == "APPROVED"

    def test_rejected(self):
        dto = ReviewDecisionIn(decision="REJECTED", comment="Неверная ссылка на НК")
        assert dto.decision == "REJECTED"

    def test_edited(self):
        dto = ReviewDecisionIn(
            decision="EDITED",
            comment="Добавил уточнение",
            edited_response="Исправленный ответ...",
        )
        assert dto.edited_response is not None

    def test_invalid_decision(self):
        with pytest.raises(Exception):
            ReviewDecisionIn(decision="MAYBE")


class TestSearchRequest:

    def test_valid(self):
        dto = SearchRequest(query="расторжение договора аренды")
        assert dto.top_k == 5  # default from DTO

    def test_custom_top_k(self):
        dto = SearchRequest(query="НДС и налоговый вычет", top_k=10)
        assert dto.top_k == 10


class TestTokenResponse:

    def test_fields(self):
        dto = TokenResponse(
            access_token="token123",
            refresh_token="refresh456",
        )
        assert dto.token_type == "bearer"
        assert dto.access_token == "token123"
