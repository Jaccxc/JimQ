"""S4 — backtests API router wiring (TDD slice 3).

Behaviour: the FastCRUD-backed backtests resource is mounted under /api/v1 and
its routes appear in the app's OpenAPI schema. A live list round-trip is opt-in
(RUN_DB_TESTS=1).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_backtests_routes_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/backtests" in paths
    assert "get" in paths["/api/v1/backtests"]
    assert "post" in paths["/api/v1/backtests"]


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)
def test_backtests_list_returns_paginated_shape():
    with TestClient(app) as client:
        resp = client.get("/api/v1/backtests")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)
