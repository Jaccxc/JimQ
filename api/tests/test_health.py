"""S4 backend skeleton — health endpoint behaviour (TDD tracer bullet).

Asserts the stripped FastAPI app boots and exposes a liveness endpoint that
returns 200 without requiring auth/users/tiers (all removed in this fork).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200


def test_health_reports_app_identity():
    """Liveness payload carries app name + version (public interface contract)."""
    with TestClient(app) as client:
        resp = client.get("/health")
    body = resp.json()
    assert body["status"] == "ok"
    assert "name" in body and "version" in body
