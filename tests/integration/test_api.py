from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestHealthEndpoints:

    def test_liveness(self, client):
        resp = client.get("/api/v1/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_models_endpoint(self, client):
        resp = client.get("/api/v1/health/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "count" in data

    def test_metrics_endpoint(self, client):
        resp = client.get("/api/v1/health/metrics")
        assert resp.status_code == 200
        assert "legalops" in resp.text


class TestAuthEndpoints:

    def test_login_empty_body(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_login_short_password(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.ru", "password": "12"},
        )
        assert resp.status_code == 422

    def test_login_invalid_email(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_login_invalid_credentials(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nouser@test.ru", "password": "wrongpassword"},
        )
        assert resp.status_code in (401, 500)

    def test_me_without_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_invalid_bearer_token(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    def test_refresh_missing_body(self, client):
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422

    def test_refresh_invalid_token(self, client):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "bad-token"},
        )
        assert resp.status_code == 401


class TestRequestEndpoints:

    def test_submit_without_auth(self, client):
        resp = client.post(
            "/api/v1/requests/",
            json={"raw_input": "Тестовый юридический запрос"},
        )
        assert resp.status_code in (401, 403)

    def test_list_without_auth(self, client):
        resp = client.get("/api/v1/requests/")
        assert resp.status_code in (401, 403)

    def test_submit_with_short_input(self, client):
        resp = client.post(
            "/api/v1/requests/",
            json={"raw_input": "кор"},  # too short (< 10)
        )
        assert resp.status_code in (401, 403, 422)


class TestPipelineEndpoints:

    def test_get_nonexistent_pipeline(self, client):
        resp = client.get("/api/v1/pipelines/00000000-0000-0000-0000-000000000000")
        assert resp.status_code in (401, 403, 404)

    def test_analytics_without_auth(self, client):
        resp = client.get("/api/v1/pipelines/analytics/summary")
        assert resp.status_code in (401, 403)


class TestKnowledgeEndpoints:

    def test_search_without_auth(self, client):
        resp = client.post(
            "/api/v1/knowledge/search",
            json={"query": "тестовый запрос"},
        )
        assert resp.status_code in (401, 403)

    def test_stats_without_auth(self, client):
        resp = client.get("/api/v1/knowledge/stats")
        assert resp.status_code in (401, 403)

    def test_list_documents_without_auth(self, client):
        resp = client.get("/api/v1/knowledge/documents")
        assert resp.status_code in (401, 403)

    def test_ingest_without_auth(self, client):
        resp = client.post("/api/v1/knowledge/ingest")
        assert resp.status_code in (401, 403, 422)


class TestEscalationEndpoints:

    def test_list_without_auth(self, client):
        resp = client.get("/api/v1/escalations/")
        assert resp.status_code in (401, 403)

    def test_get_nonexistent_escalation(self, client):
        resp = client.get("/api/v1/escalations/00000000-0000-0000-0000-000000000000")
        assert resp.status_code in (401, 403, 404)


class TestHumanReviewEndpoints:

    def test_pending_without_auth(self, client):
        resp = client.get("/api/v1/human-review/pending")
        assert resp.status_code in (401, 403)

    def test_sla_alerts_without_auth(self, client):
        resp = client.get("/api/v1/human-review/sla-alerts")
        assert resp.status_code in (401, 403)


class TestSSEEndpoint:

    def test_stream_without_auth(self, client):
        resp = client.get("/api/v1/requests/00000000-0000-0000-0000-000000000000/stream")
        assert resp.status_code in (401, 403)


class TestCORSHeaders:

    def test_cors_preflight(self, client):
        resp = client.options(
            "/api/v1/health/live",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)


class TestSecurityHeaders:

    def test_security_headers_present(self, client):
        resp = client.get("/api/v1/health/live")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_request_id_header(self, client):
        resp = client.get("/api/v1/health/live")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_response_time_header(self, client):
        resp = client.get("/api/v1/health/live")
        assert "X-Response-Time-Ms" in resp.headers
