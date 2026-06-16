"""卡 #23 (W4) — POST /api/v1/research/jobs(從 web 觸發研究 job)。

行為層測試(public interface):
- 路由 POST /api/v1/research/jobs 註冊在 app OpenAPI。
- 收到 {job_type, params} → 建 research_job 列(status=PENDING)→ XADD 命令信封
  到 command stream(DB0)→ 回 {job_id, correlation_id, status}。
- api 不 import research(經 Redis 解耦):用 dependency override 注入 fake CRUD
  與 fake redis,純驗證 endpoint 行為,不需真 DB/Redis。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jimq_core.constants import (
    COMMAND_STREAM_KEY,
    COMMAND_TYPE_BUILD_DATASET,
    COMMAND_TYPE_TRAIN,
)
from jimq_core.schemas import ResearchJobCommand

from app.main import app
from app.models.research_job import ResearchJobStatus


def test_research_jobs_route_registered_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/research/jobs" in paths
    assert "post" in paths["/api/v1/research/jobs"]


class _FakeRedis:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict]] = []

    async def xadd(self, key, fields, **kwargs):  # noqa: ANN001
        self.entries.append((key, dict(fields)))
        return b"0-1"


class _FakeCreated:
    def __init__(self, **data):
        self.__dict__.update(data)


class _FakeCrud:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, db, object, **kwargs):  # noqa: ANN001
        self.created.append(object.model_dump())
        return _FakeCreated(id=77, **object.model_dump())


@pytest.fixture
def overridden_client():
    from app.api.v1 import research as rs

    fake_redis = _FakeRedis()
    fake_crud = _FakeCrud()

    async def _fake_db():
        yield None

    app.dependency_overrides[rs.async_get_db] = _fake_db
    app.dependency_overrides[rs.get_command_redis] = lambda: fake_redis
    app.dependency_overrides[rs.get_research_job_crud] = lambda: fake_crud
    try:
        yield TestClient(app), fake_redis, fake_crud
    finally:
        app.dependency_overrides.clear()


def test_trigger_build_dataset_creates_pending_row_and_publishes(overridden_client):
    client, fake_redis, fake_crud = overridden_client
    body = {
        "job_type": "BUILD_DATASET",
        "params": {"symbol": "BTCUSDT-PERP.BINANCE", "timeframe": "1m"},
    }
    resp = client.post("/api/v1/research/jobs", json=body)
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["job_id"] == 77
    assert data["correlation_id"]
    assert data["status"] == ResearchJobStatus.PENDING.value

    # research_job 列建立(status 由 model 預設 PENDING)。
    assert len(fake_crud.created) == 1
    created = fake_crud.created[0]
    assert created["job_type"] == "BUILD_DATASET"
    assert created["correlation_id"] == data["correlation_id"]

    # 命令信封 XADD 到 command stream(DB0)。
    assert len(fake_redis.entries) == 1
    key, fields = fake_redis.entries[0]
    assert key == COMMAND_STREAM_KEY
    assert fields["command_type"] == COMMAND_TYPE_BUILD_DATASET
    cmd = ResearchJobCommand.model_validate_json(fields["payload"])
    assert cmd.job_id == 77
    assert cmd.correlation_id == data["correlation_id"]
    assert cmd.params == {"symbol": "BTCUSDT-PERP.BINANCE", "timeframe": "1m"}


def test_trigger_train_uses_train_command_type(overridden_client):
    client, fake_redis, _ = overridden_client
    body = {"job_type": "TRAIN", "params": {"model": "baseline"}}
    resp = client.post("/api/v1/research/jobs", json=body)
    assert resp.status_code == 202, resp.text
    _, fields = fake_redis.entries[0]
    assert fields["command_type"] == COMMAND_TYPE_TRAIN


def test_trigger_rejects_unknown_job_type(overridden_client):
    client, _, _ = overridden_client
    resp = client.post(
        "/api/v1/research/jobs", json={"job_type": "MINE_BITCOIN", "params": {}}
    )
    assert resp.status_code == 422
