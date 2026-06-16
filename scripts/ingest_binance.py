#!/usr/bin/env python
"""卡 #3 — 可重複執行的 Binance BTCUSDT-PERP 歷史資料 ingest 腳本。

抓 Binance USD-M 期貨公開 REST 的 klines(1m/5m)與 funding rate history,
經純函式轉成 Nautilus 物件,寫入 ParquetDataCatalog(data/catalog)。
idempotent:重複執行同一區間會先刪掉覆蓋區間再寫,不產生重複列。

用法:
    uv run python scripts/ingest_binance.py \
        --start 2024-01-01 --end 2024-01-07 --intervals 1m,5m --funding

公開資料免 API key。只連 Binance public REST,不碰本地 DB。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from nautilus_trader.model.data import BarType

from jimq_engine.catalog.binance_rest import BinanceFuturesREST
from jimq_engine.catalog.ingest import (
    ingest_bars,
    ingest_funding,
    open_catalog,
)
from jimq_engine.catalog.instruments import instrument_for

_DEFAULT_SYMBOL = "BTCUSDT-PERP.BINANCE"
# 卡 #22:bar interval -> Nautilus BarSpec 片段(由 instrument id 組出 BarType)。
_INTERVAL_SPECS = {"1m": "1-MINUTE-LAST-EXTERNAL", "5m": "5-MINUTE-LAST-EXTERNAL"}


def _bar_type_for(symbol: str, interval: str) -> BarType | None:
    """由 instrument id(symbol)+ interval 組出 BarType(支援多標的)。"""
    spec = _INTERVAL_SPECS.get(interval)
    if spec is None:
        return None
    return BarType.from_str(f"{symbol}-{spec}")


def _to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest Binance BTCUSDT-PERP history into catalog")
    p.add_argument("--start", required=True, help="UTC start date YYYY-MM-DD (inclusive)")
    p.add_argument("--end", required=True, help="UTC end date YYYY-MM-DD (inclusive)")
    p.add_argument("--intervals", default="1m", help="comma list of bar intervals (1m,5m)")
    p.add_argument("--funding", action="store_true", help="also ingest funding rate history")
    p.add_argument("--catalog", default=None, help="catalog path (default: repo data/catalog)")
    p.add_argument(
        "--symbol",
        default=_DEFAULT_SYMBOL,
        help="instrument id, e.g. BTCUSDT-PERP.BINANCE or ETHUSDT-PERP.BINANCE",
    )
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    start_ms = _to_ms(args.start)
    end_ms = _to_ms(args.end)
    intervals = [s.strip() for s in args.intervals.split(",") if s.strip()]

    catalog = open_catalog(args.catalog)
    # 由 symbol(instrument id)解析 instrument 定義(支援多標的;未支援拋 ValueError)。
    instrument = instrument_for(args.symbol)
    raw_symbol = str(instrument.raw_symbol)
    # 確保 instrument 定義在 catalog 內(查詢/backtest 需要)。
    catalog.write_data([instrument])

    client = BinanceFuturesREST()
    total = 0

    for interval in intervals:
        bar_type = _bar_type_for(args.symbol, interval)
        if bar_type is None:
            print(f"[skip] unsupported interval: {interval}", file=sys.stderr)
            continue
        raw = client.fetch_klines(raw_symbol, interval, start_ms, end_ms)
        n = ingest_bars(catalog, raw, instrument, bar_type=bar_type)
        total += n
        print(f"[bars {args.symbol} {interval}] wrote {n} bars")

    if args.funding:
        raw_f = client.fetch_funding_rates(raw_symbol, start_ms, end_ms)
        nf = ingest_funding(catalog, raw_f, instrument.id)
        total += nf
        print(f"[funding] wrote {nf} updates")

    print(f"[done] {total} records into {catalog.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
