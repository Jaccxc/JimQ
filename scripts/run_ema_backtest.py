"""卡 #4 — 可重複執行的 EMA 交叉策略 backtest demo。

從 ParquetDataCatalog(預設 data/catalog,由 scripts/ingest_binance.py 灌入)
讀 BTCUSDT-PERP 1m bars,跑雙 EMA 交叉策略 backtest,印出帳戶 / 訂單成交 /
部位報表。若 catalog 沒有資料,可先跑 ingest 腳本,或用本檔的合成模式。

用法:
    uv run python scripts/run_ema_backtest.py            # 讀真實 catalog
    uv run python scripts/run_ema_backtest.py --synthetic  # 用合成黃金交叉資料

確定性:FillModel 固定 random_seed,同輸入同結果。
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from nautilus_trader.model.identifiers import Venue

from jimq_engine.catalog.ingest import (
    BAR_TYPE_1M,
    ingest_bars,
    open_catalog,
    query_bars,
)
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.nodes.backtest import build_engine
from jimq_engine.strategies.ema_cross import EMACrossConfig

_BASE_MS = 1_700_000_000_000


def _synthetic_klines() -> list[list]:
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    prices = down + up
    out = []
    for i, p in enumerate(prices):
        ot = _BASE_MS + i * 60_000
        out.append([ot, f"{p}", f"{p + 5}", f"{p - 5}", f"{p}", "10.000",
                    ot + 59_999, "0", 1, "0", "0", "0"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="EMA cross backtest demo")
    parser.add_argument("--synthetic", action="store_true",
                        help="使用合成黃金交叉資料(不需 catalog 有資料)")
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=20)
    args = parser.parse_args()

    instrument = btcusdt_perp_binance()

    if args.synthetic:
        catalog = open_catalog()  # 仍用標準 catalog 介面,寫進預設路徑
        catalog.write_data([instrument])
        ingest_bars(catalog, _synthetic_klines(), instrument)
        bars = query_bars(catalog, bar_type=BAR_TYPE_1M)
    else:
        catalog = open_catalog()
        bars = query_bars(catalog, bar_type=BAR_TYPE_1M)

    if not bars:
        raise SystemExit(
            "catalog 無 BTCUSDT-PERP 1m bars。先跑 scripts/ingest_binance.py,"
            "或加 --synthetic 用合成資料。"
        )

    config = EMACrossConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=args.fast,
        slow_period=args.slow,
        trade_size=Decimal("0.100"),
        sl_pct=Decimal("0.01"),
        tp_pct=Decimal("0.02"),
    )

    print(f"bars: {len(bars)}  fast={args.fast} slow={args.slow}")
    engine = build_engine(instrument, bars, config)
    trader = engine.trader

    print("\n=== ACCOUNT REPORT ===")
    print(trader.generate_account_report(Venue("BINANCE")))
    print("\n=== ORDER FILLS REPORT ===")
    print(trader.generate_order_fills_report())
    print("\n=== POSITIONS REPORT ===")
    print(trader.generate_positions_report())

    print(f"\nclosed positions: {len(engine.cache.positions_closed())}")
    engine.dispose()


if __name__ == "__main__":
    main()
