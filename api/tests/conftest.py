"""卡 #8 — api 測試共用 fixture:用 nautilus 直接寫一個小 catalog。

api 不依賴 engine(僅 jimq_core + nautilus_trader),故 fixture 直接用 nautilus
原語建構 instrument + 一段 1m K 線並寫入 ParquetDataCatalog。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from nautilus_trader.model.currencies import BTC, USDT
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 與 catalog 定義一致(BTCUSDT-PERP.BINANCE,price_prec=1/size_prec=3)。
SYMBOL = "BTCUSDT-PERP.BINANCE"
BAR_TYPE_1M = "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"

_BASE_MS = 1700000000000
_NS_PER_MS = 1_000_000

# 5 根連續 1m K 線的 ts_init(奈秒),供測試斷言。
BAR_TS_NS = [(_BASE_MS + i * 60_000) * _NS_PER_MS for i in range(5)]


def _instrument() -> CryptoPerpetual:
    return CryptoPerpetual(
        instrument_id=InstrumentId(Symbol("BTCUSDT-PERP"), Venue("BINANCE")),
        raw_symbol=Symbol("BTCUSDT"),
        base_currency=BTC,
        quote_currency=USDT,
        settlement_currency=USDT,
        is_inverse=False,
        price_precision=1,
        size_precision=3,
        price_increment=Price.from_str("0.1"),
        size_increment=Quantity.from_str("0.001"),
        ts_event=0,
        ts_init=0,
        margin_init=Decimal("0"),
        margin_maint=Decimal("0"),
        maker_fee=Decimal("0.0002"),
        taker_fee=Decimal("0.0004"),
    )


@pytest.fixture
def fixture_catalog(tmp_path):
    """寫入 5 根 1m K 線並回傳 catalog 路徑(str)。"""
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = _instrument()
    catalog.write_data([instrument])

    bar_type = BarType.from_str(BAR_TYPE_1M)
    bars = [
        Bar(
            bar_type=bar_type,
            open=Price(37000.0 + i, 1),
            high=Price(37050.0 + i, 1),
            low=Price(36990.0 + i, 1),
            close=Price(37025.0 + i, 1),
            volume=Quantity(10.0, 3),
            ts_event=BAR_TS_NS[i],
            ts_init=BAR_TS_NS[i],
        )
        for i in range(5)
    ]
    catalog.write_data(bars)
    return str(tmp_path / "catalog")
