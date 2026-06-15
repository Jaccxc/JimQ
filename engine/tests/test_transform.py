"""卡 #3 — raw Binance 資料 → Nautilus 物件的純轉換邏輯(確定性,不打網路)。

只驗證 public 行為:欄位/精度正確、ts_init 單調遞增。
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.data import Bar, BarType, FundingRateUpdate

from jimq_engine.catalog.instruments import btcusdt_perp_binance
from jimq_engine.catalog.transform import (
    funding_history_to_updates,
    klines_to_bars,
)

# Binance USD-M futures kline 格式(公開 /fapi/v1/klines 回傳的單筆陣列):
# [openTime(ms), open, high, low, close, volume, closeTime(ms),
#  quoteVol, trades, takerBuyBase, takerBuyQuote, ignore]
RAW_KLINES = [
    [
        1700000000000,
        "37000.10",
        "37050.50",
        "36990.00",
        "37025.30",
        "12.345",
        1700000059999,
        "456789.0",
        100,
        "6.0",
        "222000.0",
        "0",
    ],
    [
        1700000060000,
        "37025.30",
        "37100.00",
        "37010.00",
        "37080.80",
        "8.200",
        1700000119999,
        "303000.0",
        80,
        "4.0",
        "148000.0",
        "0",
    ],
]

# Binance funding rate history 格式(公開 /fapi/v1/fundingRate):
RAW_FUNDING = [
    {"symbol": "BTCUSDT", "fundingTime": 1700000000000, "fundingRate": "0.00010000", "markPrice": "37000.0"},
    {"symbol": "BTCUSDT", "fundingTime": 1700028800000, "fundingRate": "-0.00005000", "markPrice": "37100.0"},
]


def _bar_type() -> BarType:
    return BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")


def test_klines_to_bars_field_and_precision_correct():
    instrument = btcusdt_perp_binance()
    bars = klines_to_bars(RAW_KLINES, _bar_type(), instrument)

    assert len(bars) == 2
    first = bars[0]
    assert isinstance(first, Bar)
    # OHLC 字面值正確,且精度對齊 instrument(price_precision=1)
    assert str(first.open) == "37000.1"
    assert str(first.high) == "37050.5"
    assert str(first.low) == "36990.0"  # 36990.00 -> price_precision 1 -> 36990.0
    assert str(first.close) == "37025.3"
    # volume 對齊 size_precision=3
    assert str(first.volume) == "12.345"
    # ts_event 用 open time(ms→ns)
    assert first.ts_event == 1700000000000 * 1_000_000
    assert first.ts_init == 1700000000000 * 1_000_000


def test_klines_low_precision_rounding():
    instrument = btcusdt_perp_binance()
    bars = klines_to_bars(RAW_KLINES, _bar_type(), instrument)
    # 36990.00 在 price_precision=1 下應為 36990.0
    assert str(bars[0].low) == "36990.0"


def test_klines_to_bars_ts_init_monotonic():
    instrument = btcusdt_perp_binance()
    bars = klines_to_bars(RAW_KLINES, _bar_type(), instrument)
    ts = [b.ts_init for b in bars]
    assert ts == sorted(ts)
    assert ts[0] < ts[1]


def test_funding_history_to_updates_field_correct():
    instrument = btcusdt_perp_binance()
    updates = funding_history_to_updates(RAW_FUNDING, instrument.id)

    assert len(updates) == 2
    u0 = updates[0]
    assert isinstance(u0, FundingRateUpdate)
    assert u0.instrument_id == instrument.id
    assert u0.rate == Decimal("0.00010000")
    assert u0.ts_event == 1700000000000 * 1_000_000
    # 負費率保留
    assert updates[1].rate == Decimal("-0.00005000")


def test_funding_history_ts_init_monotonic():
    instrument = btcusdt_perp_binance()
    updates = funding_history_to_updates(RAW_FUNDING, instrument.id)
    ts = [u.ts_init for u in updates]
    assert ts == sorted(ts)
