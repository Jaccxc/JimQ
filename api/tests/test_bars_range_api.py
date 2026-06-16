"""卡 — GET /api/v1/bars/range 端點(行為層測試)。

回某 symbol+timeframe 在 catalog 的實際資料區間 {start, end, count}(min/max
bar ts_init 奈秒;count = bar 根數)。空 catalog / 未知 symbol → start/end=None、
count=0。供前端 launcher 掛載時動態填有資料的預設日期(取代寫死區間)。

端點以 ``JIMQ_CATALOG_PATH`` 覆寫 catalog 路徑指向 fixture catalog。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

SYMBOL = "BTCUSDT-PERP.BINANCE"
_BASE_MS = 1700000000000
BAR_TS_NS = [(_BASE_MS + i * 60_000) * 1_000_000 for i in range(5)]


def test_bars_range_route_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/bars/range" in paths
    assert "get" in paths["/api/v1/bars/range"]


def test_bars_range_returns_span(fixture_catalog, monkeypatch):
    monkeypatch.setenv("JIMQ_CATALOG_PATH", fixture_catalog)
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/bars/range", params={"symbol": SYMBOL, "timeframe": "1m"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 5
    assert body["start"] == BAR_TS_NS[0]
    assert body["end"] == BAR_TS_NS[-1]


def test_bars_range_unknown_symbol_returns_empty(fixture_catalog, monkeypatch):
    monkeypatch.setenv("JIMQ_CATALOG_PATH", fixture_catalog)
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/bars/range",
            params={"symbol": "ETHUSDT-PERP.BINANCE", "timeframe": "1m"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"start": None, "end": None, "count": 0}
