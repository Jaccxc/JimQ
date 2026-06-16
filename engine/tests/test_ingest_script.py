"""卡 #3 — ingest 腳本端到端 wiring(不打網路:注入 fake REST)。

驗證:給定 fake raw 回應,腳本能轉換並寫入 catalog,且可查回。
"""

from __future__ import annotations

import sys
from pathlib import Path

import scripts.ingest_binance as script
from jimq_engine.catalog.ingest import open_catalog, query_bars, query_funding


def _kline_row(open_ms):
    return [open_ms, "37000.0", "37050.0", "36990.0", "37025.0", "10.0", open_ms + 59999, "0", 1, "0", "0", "0"]


class FakeClient:
    def __init__(self, *a, **k):
        pass

    def fetch_klines(self, symbol, interval, start_ms, end_ms):
        return [_kline_row(1700000000000), _kline_row(1700000060000)]

    def fetch_funding_rates(self, symbol, start_ms, end_ms):
        return [{"symbol": "BTCUSDT", "fundingTime": 1700000000000, "fundingRate": "0.0001", "markPrice": "37000"}]


def test_script_run_writes_and_queryable(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "BinanceFuturesREST", FakeClient)
    catalog_path = str(tmp_path / "catalog")

    args = script.parse_args(
        ["--start", "2023-11-14", "--end", "2023-11-15", "--intervals", "1m", "--funding", "--catalog", catalog_path]
    )
    rc = script.run(args)
    assert rc == 0

    catalog = open_catalog(catalog_path)
    assert len(query_bars(catalog)) == 2
    assert len(query_funding(catalog)) == 1


def test_script_ingests_eth_symbol_with_eth_bar_type(tmp_path, monkeypatch):
    """卡 #22:--symbol ETHUSDT-PERP.BINANCE 用 ETH instrument + ETH bar type 寫入。"""
    from nautilus_trader.model.data import BarType

    from jimq_engine.catalog.ingest import query_bars as q

    monkeypatch.setattr(script, "BinanceFuturesREST", FakeClient)
    catalog_path = str(tmp_path / "catalog")
    args = script.parse_args(
        [
            "--start", "2023-11-14", "--end", "2023-11-15",
            "--intervals", "1m", "--symbol", "ETHUSDT-PERP.BINANCE",
            "--catalog", catalog_path,
        ]
    )
    assert script.run(args) == 0

    catalog = open_catalog(catalog_path)
    eth_bt = BarType.from_str("ETHUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")
    eth_bars = q(catalog, bar_type=eth_bt)
    assert len(eth_bars) == 2
    # BTC bar type 不應有資料(未灌)。
    btc_bt = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")
    assert len(q(catalog, bar_type=btc_bt)) == 0


def test_script_idempotent_second_run(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "BinanceFuturesREST", FakeClient)
    catalog_path = str(tmp_path / "catalog")
    args = script.parse_args(["--start", "2023-11-14", "--end", "2023-11-15", "--catalog", catalog_path])

    script.run(args)
    script.run(args)  # 再跑一次

    catalog = open_catalog(catalog_path)
    assert len(query_bars(catalog)) == 2  # 不重複
