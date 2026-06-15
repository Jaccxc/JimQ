"""卡 #8 — GET /api/v1/bars 端點(行為層測試)。

- 路由註冊於 /api/v1/bars 且為 GET。
- 帶 symbol/timeframe 回傳 BarDTO 形狀的 JSON 列表(time/open/high/low/close/volume）。
- start/end 過濾切片。
- 未知 symbol 回 200 + 空列表(與 store 邊界一致)。

端點以 ``JIMQ_CATALOG_PATH`` 環境變數覆寫 catalog 路徑供測試指向 fixture catalog。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

SYMBOL = "BTCUSDT-PERP.BINANCE"
_BASE_MS = 1700000000000
BAR_TS_NS = [(_BASE_MS + i * 60_000) * 1_000_000 for i in range(5)]


def test_bars_route_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/bars" in paths
    assert "get" in paths["/api/v1/bars"]


def test_get_bars_returns_dto_list(fixture_catalog, monkeypatch):
    monkeypatch.setenv("JIMQ_CATALOG_PATH", fixture_catalog)
    with TestClient(app) as client:
        resp = client.get("/api/v1/bars", params={"symbol": SYMBOL, "timeframe": "1m"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 5
    first = body[0]
    assert set(first) == {"ts", "time", "open", "high", "low", "close", "volume"}
    assert first["open"] == "37000.0"
    assert first["time"] == BAR_TS_NS[0] // 1_000_000_000


def test_get_bars_time_slice(fixture_catalog, monkeypatch):
    monkeypatch.setenv("JIMQ_CATALOG_PATH", fixture_catalog)
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/bars",
            params={
                "symbol": SYMBOL,
                "timeframe": "1m",
                "start": BAR_TS_NS[1],
                "end": BAR_TS_NS[3],
            },
        )
    assert resp.status_code == 200
    assert [b["ts"] for b in resp.json()] == BAR_TS_NS[1:4]


def test_get_bars_unknown_symbol_returns_empty(fixture_catalog, monkeypatch):
    monkeypatch.setenv("JIMQ_CATALOG_PATH", fixture_catalog)
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/bars",
            params={"symbol": "ETHUSDT-PERP.BINANCE", "timeframe": "1m"},
        )
    assert resp.status_code == 200
    assert resp.json() == []
