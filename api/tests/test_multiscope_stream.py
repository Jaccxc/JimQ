"""卡 A — Live/Backtest 資料源隔離:api 雙 scope 並行消費 行為測試(非 gated)。

問題:live 與 backtest 共用單一 hub + 單一熱重載 supervisor(watch 唯一
``jimq:latest_stream_key``)。一跑 backtest,supervisor 把唯一 hub 切到 backtest
stream → backtest 的 buy/sell 漏進 Live 圖。

期望行為(只驗 public interface):
- ``make_multiscope_lifespan`` 在 app.state 掛上 **每 scope 各自** 的 Hub 與
  ConsumerSupervisor(``scoped_hubs`` / ``scoped_supervisors``,key 為 ``live`` /
  ``backtest``);``app.state.hub`` 維持指向 live hub(現狀相容)。
- backtest stream 的事件只進 backtest hub,**不**進 live hub(反之亦然)——
  兩 supervisor 並行各 watch 自己的 latest-key,互不污染。
- lifespan 結束乾淨關閉:兩 supervisor 都收尾、task 正常結束(非 cancelled)。
- WS gateway 依 ``scope`` query 路由到對應 hub;預設(未帶 scope)走 live(相容)。

用一個 FakeMultiScopeRedis(兩 stream + 兩 latest-key)+ 真 run_consumer /
ConsumerSupervisor,測試快且確定性,不真等秒數、不需真 Redis。
"""

from __future__ import annotations

import asyncio

import msgspec
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from jimq_core.constants import (
    BACKTEST_LATEST_STREAM_KEY,
    LIVE_LATEST_STREAM_KEY,
    STREAM_SCOPE_BACKTEST,
    STREAM_SCOPE_LIVE,
)

from app.services.hub import Hub
from app.ws.app_factory import make_multiscope_lifespan
from app.ws.stream import register_ws


def _bar_entry(entry_id: str, close: str):
    return (
        entry_id.encode(),
        {
            b"topic": b"data.bars.BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
            b"payload": msgspec.msgpack.encode(
                {
                    "type": "Bar",
                    "open": close, "high": close, "low": close, "close": close,
                    "volume": "1", "ts_event": "1700000000000000000",
                    "ts_init": "1700000000000000000",
                }
            ),
        },
    )


class FakeMultiScopeRedis:
    """兩 stream + 兩 latest-key 的 fake。

    - ``get(latest_key)``:回該 scope 目前指向的 stream key(或 None)。
    - ``xreadgroup({key:'0'})``:回該 stream backlog(一次給完);``'>'`` 回空。
    - ``set_latest(latest_key, stream_key)``:測試切換某 scope 指向。
    """

    def __init__(self, streams: dict[str, list]):
        self._streams = streams
        self._latest: dict[str, str] = {}
        self._gave: dict[str, bool] = {}
        self.acked: list[bytes] = []

    def set_latest(self, latest_key: str, stream_key: str | None) -> None:
        if stream_key is None:
            self._latest.pop(latest_key, None)
        else:
            self._latest[latest_key] = stream_key

    async def get(self, key):
        v = self._latest.get(key)
        return None if v is None else v.encode()

    async def xgroup_create(self, *a, **k):
        return True

    async def xreadgroup(self, group, consumer, streams, count=100, block=1000):
        ((key, read_id),) = streams.items()
        if read_id == "0":
            if not self._gave.get(key):
                self._gave[key] = True
                return [(key.encode(), list(self._streams.get(key, [])))]
            return []
        await asyncio.sleep(0)
        return []

    async def xack(self, key, group, entry_id):
        self.acked.append(entry_id)

    async def aclose(self):
        return None


async def _wait_for(pred, *, tries=500):
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(0.001)
    return False


def _closes(hub: Hub) -> list[str]:
    return [e["data"]["close"] for e in hub.snapshot({"bars"})]


@pytest.mark.asyncio
async def test_multiscope_lifespan_creates_per_scope_hub_and_supervisor():
    client = FakeMultiScopeRedis({})
    app = FastAPI()
    lifespan = make_multiscope_lifespan(client=client, poll_interval=0.0)
    async with lifespan(app):
        scoped = app.state.scoped_hubs
        assert set(scoped) == {STREAM_SCOPE_LIVE, STREAM_SCOPE_BACKTEST}
        assert isinstance(scoped[STREAM_SCOPE_LIVE], Hub)
        assert isinstance(scoped[STREAM_SCOPE_BACKTEST], Hub)
        # live 與 backtest 是不同 hub 實例。
        assert scoped[STREAM_SCOPE_LIVE] is not scoped[STREAM_SCOPE_BACKTEST]
        # 相容:app.state.hub 仍指向 live hub。
        assert app.state.hub is scoped[STREAM_SCOPE_LIVE]
        assert set(app.state.scoped_supervisors) == {
            STREAM_SCOPE_LIVE,
            STREAM_SCOPE_BACKTEST,
        }


@pytest.mark.asyncio
async def test_backtest_events_only_reach_backtest_hub_not_live():
    """核心隔離:backtest stream 事件只進 backtest hub,不污染 live hub。"""
    client = FakeMultiScopeRedis(
        {
            "live-stream": [_bar_entry("1-0", "111")],
            "bt-stream": [_bar_entry("1-0", "222")],
        }
    )
    app = FastAPI()
    lifespan = make_multiscope_lifespan(client=client, poll_interval=0.0)
    async with lifespan(app):
        live_hub = app.state.scoped_hubs[STREAM_SCOPE_LIVE]
        bt_hub = app.state.scoped_hubs[STREAM_SCOPE_BACKTEST]

        # 只發 backtest 的 latest-key → 只 backtest hub 收到。
        client.set_latest(BACKTEST_LATEST_STREAM_KEY, "bt-stream")
        assert await _wait_for(lambda: _closes(bt_hub) == ["222"])
        assert _closes(live_hub) == []  # live 不被污染。

        # 再發 live latest-key → live hub 收到 live,backtest 不變。
        client.set_latest(LIVE_LATEST_STREAM_KEY, "live-stream")
        assert await _wait_for(lambda: _closes(live_hub) == ["111"])
        assert _closes(bt_hub) == ["222"]
        assert "222" not in _closes(live_hub)
        assert "111" not in _closes(bt_hub)


@pytest.mark.asyncio
async def test_both_supervisors_clean_shutdown():
    client = FakeMultiScopeRedis({"bt-stream": [_bar_entry("1-0", "222")]})
    app = FastAPI()
    lifespan = make_multiscope_lifespan(client=client, poll_interval=0.0)
    async with lifespan(app):
        client.set_latest(BACKTEST_LATEST_STREAM_KEY, "bt-stream")
        bt_hub = app.state.scoped_hubs[STREAM_SCOPE_BACKTEST]
        assert await _wait_for(lambda: _closes(bt_hub) == ["222"])
        live_task = app.state.scoped_supervisor_tasks[STREAM_SCOPE_LIVE]
        bt_task = app.state.scoped_supervisor_tasks[STREAM_SCOPE_BACKTEST]
    # 離開 lifespan 後兩 supervisor task 都收尾且非 cancelled。
    assert live_task.done() and not live_task.cancelled()
    assert bt_task.done() and not bt_task.cancelled()


def test_ws_routes_by_scope_and_defaults_to_live():
    """WS gateway 依 scope query 路由到對應 hub;未帶 scope 預設 live。"""
    live_hub = Hub()
    bt_hub = Hub()
    app = FastAPI()
    app.state.scoped_hubs = {
        STREAM_SCOPE_LIVE: live_hub,
        STREAM_SCOPE_BACKTEST: bt_hub,
    }
    app.state.hub = live_hub  # 相容預設。
    register_ws(app)

    def _drain_until_live(ws):
        out = []
        while True:
            m = ws.receive_json()
            if m.get("type") == "live":
                return out
            out.append(m)

    with TestClient(app) as client:
        # scope=backtest 的連線只收 backtest hub 的事件,不收 live hub。
        with client.websocket_connect(
            "/ws/stream?channels=bars&scope=backtest"
        ) as ws:
            _drain_until_live(ws)
            client.portal.call(
                live_hub.publish,
                {"channel": "bars", "seq": 1, "data": {"close": "LIVE"}},
            )
            client.portal.call(
                bt_hub.publish,
                {"channel": "bars", "seq": 2, "data": {"close": "BT"}},
            )
            m = ws.receive_json()
            assert m["data"]["close"] == "BT"

        # 未帶 scope → 預設 live hub。
        with client.websocket_connect("/ws/stream?channels=bars") as ws:
            _drain_until_live(ws)
            client.portal.call(
                live_hub.publish,
                {"channel": "bars", "seq": 3, "data": {"close": "LIVE2"}},
            )
            m = ws.receive_json()
            assert m["data"]["close"] == "LIVE2"
