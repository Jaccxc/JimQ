"""BTCUSDT-PERP.BINANCE 的 Nautilus instrument 定義(卡 #3)。

精度依 Binance USD-M 期貨實際規格:price_precision=1(tickSize 0.1)、
size_precision=3(stepSize 0.001)。用單一 factory 確保 ingest 與查詢用同一份定義。
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.currencies import BTC, USDT
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.objects import Price, Quantity

# InstrumentId 慣例:BTCUSDT-PERP.BINANCE
BTCUSDT_PERP_BINANCE_ID = InstrumentId(Symbol("BTCUSDT-PERP"), Venue("BINANCE"))


def btcusdt_perp_binance(ts_init: int = 0) -> CryptoPerpetual:
    """建構 Binance USD-M BTCUSDT 永續合約 instrument 定義。"""
    return CryptoPerpetual(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        raw_symbol=Symbol("BTCUSDT"),
        base_currency=BTC,
        quote_currency=USDT,
        settlement_currency=USDT,
        is_inverse=False,
        price_precision=1,
        size_precision=3,
        price_increment=Price.from_str("0.1"),
        size_increment=Quantity.from_str("0.001"),
        ts_event=ts_init,
        ts_init=ts_init,
        margin_init=Decimal("0"),
        margin_maint=Decimal("0"),
        maker_fee=Decimal("0.0002"),
        taker_fee=Decimal("0.0004"),
    )
