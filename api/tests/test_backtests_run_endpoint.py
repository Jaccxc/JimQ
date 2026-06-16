"""卡 #20 (W1) — POST /api/v1/backtests/run(從 UI 觸發 backtest)。

行為層測試(public interface):
- 路由 POST /api/v1/backtests/run 註冊在 app OpenAPI。
- 收到 {symbol,timeframe,strategy,params,start,end} → 建 backtest_run 列
  (status=PENDING)→ XADD 命令信封到 command stream(DB0)→ 回 {run_id,
  correlation_id}。
- api 不 import engine(經 Redis 解耦):用 dependency override 注入 fake CRUD
  與 fake redis,純驗證 endpoint 行為,不需真 DB/Redis。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jimq_core.constants import COMMAND_STREAM_KEY, COMMAND_TYPE_RUN_BACKTEST
from jimq_core.schemas import RunBacktestCommand

from app.main import app
from app.models.backtest_run import BacktestStatus


def test_run_route_registered_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/backtests/run" in paths
    assert "post" in paths["/api/v1/backtests/run"]


class _FakeRedis:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict]] = []

    async def xadd(self, key, fields, **kwargs):  # noqa: ANN001
        self.entries.append((key, dict(fields)))
        return b"0-1"


class _FakeCreated:
    """模擬 FastCRUD create 回傳的 row(帶自增 id)。"""

    def __init__(self, **data):
        self.__dict__.update(data)


class _FakeCrud:
    """記錄 create 呼叫並回傳帶 id 的 row。"""

    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, db, object, **kwargs):  # noqa: ANN001
        self.created.append(object.model_dump())
        return _FakeCreated(id=123, **object.model_dump())


@pytest.fixture
def overridden_client():
    from app.api.v1 import backtests as bt

    fake_redis = _FakeRedis()
    fake_crud = _FakeCrud()

    async def _fake_db():
        yield None

    app.dependency_overrides[bt.async_get_db] = _fake_db
    app.dependency_overrides[bt.get_command_redis] = lambda: fake_redis
    app.dependency_overrides[bt.get_backtest_crud] = lambda: fake_crud
    try:
        yield TestClient(app), fake_redis, fake_crud
    finally:
        app.dependency_overrides.clear()


def test_run_creates_pending_row_and_publishes_command(overridden_client):
    client, fake_redis, fake_crud = overridden_client
    body = {
        "symbol": "BTCUSDT-PERP.BINANCE",
        "timeframe": "1m",
        "strategy": "ema_cross",
        "params": {"fast_period": 3, "slow_period": 8},
        "start": "2023-11-14T22:13:20Z",
        "end": "2023-11-14T23:13:20Z",
    }
    resp = client.post("/api/v1/backtests/run", json=body)
    assert resp.status_code == 202, resp.text
    data = resp.json()
    run_id = data["run_id"]
    assert run_id == 123
    assert data["correlation_id"]
    assert data["status"] == BacktestStatus.PENDING.value

    # backtest_run 列以使用者欄位建立(status 由 model 預設 PENDING,回應已明示)。
    assert len(fake_crud.created) == 1
    created = fake_crud.created[0]
    assert created["strategy_name"] == "ema_cross"
    assert created["instrument_id"] == "BTCUSDT-PERP.BINANCE"
    assert created["bar_type"] == "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"
    assert created["correlation_id"] == data["correlation_id"]

    # 命令信封 XADD 到 command stream(DB0 另一條 key)。
    assert len(fake_redis.entries) == 1
    key, fields = fake_redis.entries[0]
    assert key == COMMAND_STREAM_KEY
    assert fields["command_type"] == COMMAND_TYPE_RUN_BACKTEST
    cmd = RunBacktestCommand.model_validate_json(fields["payload"])
    assert cmd.run_id == run_id
    assert cmd.correlation_id == data["correlation_id"]
    assert cmd.strategy == "ema_cross"
    assert cmd.params == {"fast_period": 3, "slow_period": 8}
