"""卡 #30 (P2-S1b) — GET /api/v1/live/bars 端點(行為層測試)。

Live 頁初始載入用的「近期真 klines」端點:從 Binance USDT-M 期貨 **testnet**
公開 klines REST(``testnet.binancefuture.com/fapi/v1/klines``)取最近 N 根,
映射成共用契約 ``BarDTO`` 列表回出(與 live WS bar 同 venue,價位一致 ~66k)。

設計(對齊 mlflow proxy 慣例):
- api **不 import engine**;經注入的 async HTTP client(httpx-like)打公開 klines
  REST(免金鑰),測試 override 成 fake client,不需真網路。
- symbol 形如 ``BTCUSDT-PERP.BINANCE``(前端 instrument_id)→ 取 Binance raw
  symbol ``BTCUSDT`` 打 klines。
- 回 BarDTO 形狀:``ts``(epoch 奈秒)、``time``(epoch 秒,餵 LWC)、字串 OHLCV。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.live_bars import get_klines_http

# Binance klines raw row 形狀(public REST):
#   [openTime(ms), open, high, low, close, volume, closeTime, ...]
_OPEN_MS = 1700000000000
_RAW_ROWS = [
    [
        _OPEN_MS + i * 60_000,
        f"{66000 + i}.0",
        f"{66010 + i}.0",
        f"{65990 + i}.0",
        f"{66005 + i}.0",
        f"{1.5 + i}",
        _OPEN_MS + i * 60_000 + 59_999,
        "0",
        0,
        "0",
        "0",
        "0",
    ]
    for i in range(3)
]


class _FakeResponse:
    def __init__(self, payload: list) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list:
        return self._payload


class _FakeKlinesClient:
    """記錄請求並回固定 Binance klines 形狀 raw rows(不需真網路)。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, params=None, **kwargs):  # noqa: ANN001
        self.calls.append((url, params or {}))
        return _FakeResponse(_RAW_ROWS)

    async def aclose(self) -> None:
        return None


def test_live_bars_route_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/live/bars" in paths
    assert "get" in paths["/api/v1/live/bars"]


def test_live_bars_returns_dto_list_from_klines():
    fake = _FakeKlinesClient()
    app.dependency_overrides[get_klines_http] = lambda: fake
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/live/bars",
                params={"symbol": "BTCUSDT-PERP.BINANCE", "timeframe": "1m", "limit": 3},
            )
    finally:
        app.dependency_overrides.pop(get_klines_http, None)

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 3
    first = body[0]
    assert set(first) == {"ts", "time", "open", "high", "low", "close", "volume"}
    # OHLCV 以字串保留交易所精度。
    assert first["open"] == "66000.0"
    assert first["close"] == "66005.0"
    assert first["volume"] == "1.5"
    # time = epoch 秒(LWC),ts = epoch 奈秒。
    assert first["time"] == _OPEN_MS // 1000
    assert first["ts"] == _OPEN_MS * 1_000_000


def test_live_bars_calls_testnet_klines_with_raw_symbol():
    """打 testnet 期貨公開 klines,symbol 取 raw(BTCUSDT),帶 interval/limit。"""
    fake = _FakeKlinesClient()
    app.dependency_overrides[get_klines_http] = lambda: fake
    try:
        with TestClient(app) as client:
            client.get(
                "/api/v1/live/bars",
                params={"symbol": "BTCUSDT-PERP.BINANCE", "timeframe": "1m", "limit": 50},
            )
    finally:
        app.dependency_overrides.pop(get_klines_http, None)

    assert len(fake.calls) == 1
    url, params = fake.calls[0]
    # 同 live venue:testnet 期貨公開 klines。
    assert "testnet.binancefuture.com" in url
    assert url.endswith("/fapi/v1/klines")
    assert params["symbol"] == "BTCUSDT"
    assert params["interval"] == "1m"
    assert params["limit"] == 50
