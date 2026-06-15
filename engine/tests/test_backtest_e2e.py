"""卡 #4 — 小型 end-to-end backtest(catalog → backtest → reports)。

驗收:
- 從 ParquetDataCatalog 讀 BTCUSDT-PERP bars 跑 backtest。
- 產出帳戶 / 訂單成交 / 部位報表,且確有交易發生(完整生命週期)。
- 確定性:同輸入(含 FillModel random_seed)同結果。

合成資料寫進臨時 catalog(不打網路),製造一次黃金交叉確保有成交。
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.identifiers import Venue
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_engine.catalog.ingest import (
    BAR_TYPE_1M,
    ingest_bars,
    query_bars,
)
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.nodes.backtest import build_engine
from jimq_engine.strategies.ema_cross import EMACrossConfig

_BASE_MS = 1_700_000_000_000


def _golden_cross_klines() -> list[list]:
    """合成 Binance kline 陣列:緩跌後急漲 → 黃金交叉。"""
    down = [40000.0 - i * 20 for i in range(15)]
    up = [down[-1] + i * 120 for i in range(1, 20)]
    prices = down + up
    klines = []
    for i, p in enumerate(prices):
        ot = _BASE_MS + i * 60_000
        klines.append(
            [ot, f"{p}", f"{p + 5}", f"{p - 5}", f"{p}", "10.000",
             ot + 59_999, "0", 1, "0", "0", "0"]
        )
    return klines


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


def _run_from_catalog(tmp_path, seed: int = 42):
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])
    ingest_bars(catalog, _golden_cross_klines(), instrument)

    bars = query_bars(catalog, bar_type=BAR_TYPE_1M)
    assert len(bars) == 34
    return build_engine(instrument, bars, _config(), random_seed=seed)


def test_e2e_reports_show_trades(tmp_path):
    engine = _run_from_catalog(tmp_path)
    trader = engine.trader

    account_report = trader.generate_account_report(Venue("BINANCE"))
    fills_report = trader.generate_order_fills_report()
    positions_report = trader.generate_positions_report()

    # 確有交易發生:有成交、有部位。
    assert not fills_report.empty, "應有訂單成交報表列"
    assert not positions_report.empty, "應有部位報表列"
    assert not account_report.empty, "應有帳戶報表列"

    engine.dispose()


def test_e2e_full_lifecycle_position_closed(tmp_path):
    engine = _run_from_catalog(tmp_path)
    closed = engine.cache.positions_closed()
    assert len(closed) >= 1, "完整生命週期:進場成交→部位→出場(平倉)"
    engine.dispose()


def test_e2e_deterministic_same_input_same_result(tmp_path):
    """同輸入(同 seed)兩次跑 → 帳戶餘額完全一致。"""
    e1 = _run_from_catalog(tmp_path / "a", seed=7)
    e2 = _run_from_catalog(tmp_path / "b", seed=7)

    bal1 = e1.trader.generate_account_report(Venue("BINANCE"))
    bal2 = e2.trader.generate_account_report(Venue("BINANCE"))

    assert bal1.to_dict() == bal2.to_dict()

    e1.dispose()
    e2.dispose()
