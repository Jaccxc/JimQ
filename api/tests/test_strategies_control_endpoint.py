"""卡 #24 (W5) — 策略控制端點(POST /api/v1/strategies/{id}/start|stop、POST /api/v1/kill)。

行為層測試(public interface):
- 三個路由註冊在 app OpenAPI。
- POST /strategies/{id}/start → 發 START_STRATEGY 控制命令信封到 command stream
  (DB0),帶 strategy_id + params + correlation_id;回 202 + {strategy_id,
  command_type, correlation_id}。
- POST /strategies/{id}/stop → 發 STOP_STRATEGY 控制命令。
- POST /kill → 發 KILL 全域急停命令(strategy_id 省略)。
- api 不 import engine(經 Redis 解耦):用 dependency override 注入 fake redis,
  純驗 endpoint 行為,不需真 Redis。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jimq_core.constants import (
    COMMAND_STREAM_KEY,
    COMMAND_TYPE_KILL,
    COMMAND_TYPE_START_STRATEGY,
    COMMAND_TYPE_STOP_STRATEGY,
)
from jimq_core.schemas import ControlCommand

from app.main import app


def test_control_routes_registered_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/strategies/{strategy_id}/start" in paths
    assert "/api/v1/strategies/{strategy_id}/stop" in paths
    assert "/api/v1/kill" in paths
    assert "post" in paths["/api/v1/strategies/{strategy_id}/start"]
    assert "post" in paths["/api/v1/kill"]


class _FakeRedis:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict]] = []

    async def xadd(self, key, fields, **kwargs):  # noqa: ANN001
        self.entries.append((key, dict(fields)))
        return b"0-1"


@pytest.fixture
def overridden_client():
    from app.api.v1 import strategies as st

    fake_redis = _FakeRedis()
    app.dependency_overrides[st.get_command_redis] = lambda: fake_redis
    try:
        yield TestClient(app), fake_redis
    finally:
        app.dependency_overrides.clear()


def test_start_publishes_start_command(overridden_client):
    client, fake_redis = overridden_client
    resp = client.post(
        "/api/v1/strategies/ema_cross/start", json={"params": {"fast_period": 3}}
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["strategy_id"] == "ema_cross"
    assert data["command_type"] == COMMAND_TYPE_START_STRATEGY
    assert data["correlation_id"]

    assert len(fake_redis.entries) == 1
    key, fields = fake_redis.entries[0]
    assert key == COMMAND_STREAM_KEY
    assert fields["command_type"] == COMMAND_TYPE_START_STRATEGY
    cmd = ControlCommand.model_validate_json(fields["payload"])
    assert cmd.strategy_id == "ema_cross"
    assert cmd.params == {"fast_period": 3}
    assert cmd.correlation_id == data["correlation_id"]


def test_start_without_body_publishes_empty_params(overridden_client):
    client, fake_redis = overridden_client
    resp = client.post("/api/v1/strategies/ema_cross/start")
    assert resp.status_code == 202, resp.text
    _, fields = fake_redis.entries[0]
    cmd = ControlCommand.model_validate_json(fields["payload"])
    assert cmd.params == {}


def test_stop_publishes_stop_command(overridden_client):
    client, fake_redis = overridden_client
    resp = client.post("/api/v1/strategies/ema_cross/stop")
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["command_type"] == COMMAND_TYPE_STOP_STRATEGY
    _, fields = fake_redis.entries[0]
    assert fields["command_type"] == COMMAND_TYPE_STOP_STRATEGY
    cmd = ControlCommand.model_validate_json(fields["payload"])
    assert cmd.strategy_id == "ema_cross"


def test_kill_publishes_global_kill_command(overridden_client):
    client, fake_redis = overridden_client
    resp = client.post("/api/v1/kill")
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["command_type"] == COMMAND_TYPE_KILL
    assert data["correlation_id"]
    _, fields = fake_redis.entries[0]
    assert fields["command_type"] == COMMAND_TYPE_KILL
    cmd = ControlCommand.model_validate_json(fields["payload"])
    assert cmd.command_type == COMMAND_TYPE_KILL
    assert cmd.strategy_id is None
