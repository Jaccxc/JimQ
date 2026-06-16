"""卡 #7 — WS gateway 邊界 deep module 測試。

行為級驗收(用 starlette TestClient websocket_connect):
- 多工分派:client 只收到自己訂的 channel。
- 連線即推**快照**(snapshot 標記),之後推 **delta**(無 snapshot 標記)。
- 有界佇列溢出(drop-oldest / pnl last-value-wins)— 由 hub 保證,gateway 沿用。
- ``last_seq`` 重連補洞:帶 last_seq 連線先回補缺口(不重複不遺漏)再續 delta。
- 心跳:閒置時 server 週期送 heartbeat。

gateway 用一個可注入的 hub(app.state.hub),測試直接對 hub publish 驗證端到端
分派,不需真 Redis。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.services.hub import Hub
from app.ws.stream import register_ws


def _env(channel: str, seq: int, **data) -> dict:
    return {"channel": channel, "seq": seq, "data": {**data}}


def _make_app(hub: Hub) -> FastAPI:
    app = FastAPI()
    app.state.hub = hub
    register_ws(app)
    return app


def _drain_until_live(ws) -> list[dict]:
    """收到 'live' 控制訊息(快照/補洞結束)前的所有資料訊息。"""
    msgs = []
    while True:
        m = ws.receive_json()
        if m.get("type") == "live":
            return msgs
        msgs.append(m)


def test_snapshot_on_connect_then_delta():
    """連線先收快照(snapshot 標記),live 後收 delta。"""
    hub = Hub(bars_history=10)
    app = _make_app(hub)
    with TestClient(app) as client:
        # 先灌兩根 bar 進快照狀態(用同步 helper)。
        client.portal.call(hub.publish, _env("bars", 1, close="100"))
        client.portal.call(hub.publish, _env("bars", 2, close="200"))
        with client.websocket_connect("/ws/stream?channels=bars") as ws:
            snap = _drain_until_live(ws)
            assert [m["data"]["close"] for m in snap] == ["100", "200"]
            assert all(m.get("snapshot") is True for m in snap)
            # 連線後的新事件 → delta(無 snapshot 標記)。
            client.portal.call(hub.publish, _env("bars", 3, close="300"))
            delta = ws.receive_json()
            assert delta["data"]["close"] == "300"
            assert not delta.get("snapshot")


def test_multiplex_only_subscribed_channel():
    """只訂 pnl → 不收 bars。"""
    hub = Hub()
    app = _make_app(hub)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/stream?channels=pnl") as ws:
            _drain_until_live(ws)
            client.portal.call(hub.publish, _env("bars", 1, close="x"))
            client.portal.call(hub.publish, _env("pnl", 2, total="999"))
            m = ws.receive_json()
            assert m["channel"] == "pnl"
            assert m["data"]["total"] == "999"


def test_backfill_on_reconnect_with_last_seq():
    """帶 last_seq 重連:先回補 (last_seq, latest] 缺口,不重複不遺漏。"""
    hub = Hub(history=100, bars_history=0)
    app = _make_app(hub)
    with TestClient(app) as client:
        for i in range(1, 6):
            client.portal.call(hub.publish, _env("bars", i, close=str(i)))
        # client 之前看到 seq=3,重連回補 4,5。
        with client.websocket_connect(
            "/ws/stream?channels=bars&last_seq=3"
        ) as ws:
            backfilled = _drain_until_live(ws)
            assert [m["seq"] for m in backfilled] == [4, 5]


def test_trades_channel_delta_streamed():
    """卡 B:訂 trades → 收到逐筆成交 delta(視覺次秒串流端到端)。

    bars 與 trades 是兩條獨立 channel:只訂 trades 的 client 收 trades,不收 bars。
    """
    hub = Hub()
    app = _make_app(hub)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/stream?channels=trades") as ws:
            _drain_until_live(ws)
            client.portal.call(hub.publish, _env("bars", 1, close="x"))
            client.portal.call(
                hub.publish, _env("trades", 2, time=1700000005, price="40001.5")
            )
            m = ws.receive_json()
            assert m["channel"] == "trades"
            assert m["data"]["price"] == "40001.5"
            assert m["data"]["time"] == 1700000005


def test_heartbeat_sent_when_idle():
    """閒置時收到 heartbeat 控制訊息。"""
    hub = Hub()
    app = _make_app(hub)
    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/stream?channels=bars&heartbeat_s=0.1"
        ) as ws:
            _drain_until_live(ws)
            # 閒置 → 應收到至少一個 heartbeat。
            m = ws.receive_json()
            assert m["type"] == "heartbeat"
