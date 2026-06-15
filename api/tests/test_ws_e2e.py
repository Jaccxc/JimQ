"""卡 #7 — 端到端:#5 backtest 事件 → consumer → hub → WS client。

跑 #5 的 streaming backtest 把真實事件灌進本機 Redis Streams(DB0),啟動
api app(lifespan 拉起 consumer task 讀該 stream),WS client 連上後應收到
正規化的事件序列(涵蓋 bars/fills/positions/pnl)。

需本機 docker Redis(DB0)+ engine(僅測試用,api 套件本身不依賴 engine)。
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

redis = pytest.importorskip("redis")

from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars, query_bars  # noqa: E402
from jimq_engine.catalog.instruments import (  # noqa: E402
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.strategies.ema_cross import EMACrossConfig  # noqa: E402
from jimq_engine.streaming.redis_bus import (  # noqa: E402
    build_streaming_engine,
    stream_key_for,
)

from app.ws.app_factory import build_streaming_app  # noqa: E402

_BASE_MS = 1_700_000_000_000


def _redis_client():
    try:
        c = redis.Redis(host="localhost", port=6379, db=0)
        c.ping()
    except Exception:  # noqa: BLE001
        pytest.skip("本機 Redis(localhost:6379)未啟動,跳過 e2e")
    return c


def _golden_cross_klines():
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    prices = down + up
    out = []
    for i, p in enumerate(prices):
        ot = _BASE_MS + i * 60_000
        out.append(
            [ot, f"{p}", f"{p + 5}", f"{p - 5}", f"{p}", "10.000",
             ot + 59_999, "0", 1, "0", "0", "0"]
        )
    return out


def _config():
    return EMACrossConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=3,
        slow_period=8,
        trade_size=Decimal("0.100"),
        sl_pct=Decimal("0.01"),
        tp_pct=Decimal("0.02"),
    )


@pytest.fixture()
def stream_key(tmp_path):
    from nautilus_trader.persistence.catalog import ParquetDataCatalog

    client = _redis_client()
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])
    ingest_bars(catalog, _golden_cross_klines(), instrument)
    bars = query_bars(catalog, bar_type=BAR_TYPE_1M)

    engine = build_streaming_engine(instrument, bars, _config())
    key = stream_key_for(engine)
    for _ in range(50):
        if client.exists(key) and client.xlen(key) > 0:
            break
        time.sleep(0.05)
    try:
        yield key
    finally:
        engine.dispose()
        time.sleep(0.2)
        client.delete(key)
        client.close()


def test_e2e_backtest_to_ws_client(stream_key):
    """WS client 收到正規化事件序列,涵蓋 bars/fills/positions/pnl。"""
    app = build_streaming_app(stream_key=stream_key)
    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/stream?channels=bars,orders,fills,positions,pnl"
        ) as ws:
            channels_seen: set[str] = set()
            types_seen: set[str] = set()
            deadline = time.time() + 10
            # 收到夠多事件或逾時為止。
            while time.time() < deadline and not {
                "bars",
                "fills",
                "positions",
                "pnl",
            } <= channels_seen:
                msg = ws.receive_json()
                if msg.get("type") in {"live", "heartbeat"}:
                    continue
                channels_seen.add(msg["channel"])
                t = msg["data"].get("type")
                if t:
                    types_seen.add(t)

    assert "bars" in channels_seen, f"缺 bars;見到 {channels_seen}"
    assert "fills" in channels_seen, f"缺 fills;見到 {channels_seen}"
    assert "positions" in channels_seen, f"缺 positions;見到 {channels_seen}"
    assert "pnl" in channels_seen, f"缺 pnl;見到 {channels_seen}"
    assert "OrderFilled" in types_seen
    assert "AccountState" in types_seen
    assert {"PositionOpened", "PositionClosed"} & types_seen
