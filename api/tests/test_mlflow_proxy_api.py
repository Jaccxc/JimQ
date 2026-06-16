"""卡 #23 (W4) — MLflow 讀取 proxy 端點(api 經 HTTP 連 MLflow,不 import mlflow)。

行為層測試(public interface):
- 路由註冊在 app OpenAPI:
    GET /api/v1/mlflow/experiments
    GET /api/v1/mlflow/runs?experiment_id=<id>
- experiments 端點代理 MLflow REST ``experiments/search`` → 回 [{experiment_id,
  name, ...}]。
- runs 端點代理 MLflow REST ``runs/search`` → 回攤平的 [{run_id, status,
  params:{}, metrics:{}}](前端比較直接吃)。
- api 不 import ``mlflow``;經注入的 async HTTP client(httpx-like)打 REST API,
  測試 override 成 fake client,不需真 MLflow 服務。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_mlflow_routes_registered_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/mlflow/experiments" in paths
    assert "get" in paths["/api/v1/mlflow/experiments"]
    assert "/api/v1/mlflow/runs" in paths
    assert "get" in paths["/api/v1/mlflow/runs"]


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:  # noqa: D401
        return None

    def json(self) -> dict:
        return self._payload


class _FakeMlflowClient:
    """記錄請求並回固定 MLflow REST 形狀 payload(不需真服務)。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def post(self, url, json=None, **kwargs):  # noqa: ANN001
        self.calls.append((url, json or {}))
        if url.endswith("experiments/search"):
            return _FakeResponse(
                {
                    "experiments": [
                        {"experiment_id": "1", "name": "backtest", "lifecycle_stage": "active"},
                        {"experiment_id": "2", "name": "train", "lifecycle_stage": "active"},
                    ]
                }
            )
        if url.endswith("runs/search"):
            return _FakeResponse(
                {
                    "runs": [
                        {
                            "info": {
                                "run_id": "abc123",
                                "run_name": "ema-3-8",
                                "experiment_id": "1",
                                "status": "FINISHED",
                                "start_time": 1700000000000,
                            },
                            "data": {
                                "params": [
                                    {"key": "fast_period", "value": "3"},
                                    {"key": "slow_period", "value": "8"},
                                ],
                                "metrics": [
                                    {"key": "sharpe", "value": 1.5},
                                    {"key": "total_return", "value": 0.1},
                                ],
                            },
                        }
                    ]
                }
            )
        return _FakeResponse({})

    async def aclose(self) -> None:  # noqa: D401
        return None


@pytest.fixture
def overridden_client():
    from app.api.v1 import mlflow as mf

    fake = _FakeMlflowClient()
    app.dependency_overrides[mf.get_mlflow_http] = lambda: fake
    try:
        yield TestClient(app), fake
    finally:
        app.dependency_overrides.clear()


def test_experiments_endpoint_proxies_and_lists(overridden_client):
    client, fake = overridden_client
    resp = client.get("/api/v1/mlflow/experiments")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {e["name"] for e in body} == {"backtest", "train"}
    assert {e["experiment_id"] for e in body} == {"1", "2"}
    # proxied to MLflow REST experiments/search
    assert any(url.endswith("experiments/search") for url, _ in fake.calls)


def test_runs_endpoint_flattens_params_and_metrics(overridden_client):
    client, fake = overridden_client
    resp = client.get("/api/v1/mlflow/runs", params={"experiment_id": "1"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    run = body[0]
    assert run["run_id"] == "abc123"
    assert run["run_name"] == "ema-3-8"
    assert run["status"] == "FINISHED"
    # params / metrics flattened from MLflow's list-of-{key,value} into dicts
    assert run["params"] == {"fast_period": "3", "slow_period": "8"}
    assert run["metrics"] == {"sharpe": 1.5, "total_return": 0.1}
    # the experiment_id filter is forwarded to MLflow runs/search
    url, payload = next(c for c in fake.calls if c[0].endswith("runs/search"))
    assert payload["experiment_ids"] == ["1"]
