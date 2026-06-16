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


# 卡 #20 (W1):symbol 字串 -> instrument factory(command worker 用)。
# W1 先支援 BTCUSDT-PERP.BINANCE;新增標的在此註冊(預留擴充)。
_INSTRUMENT_FACTORIES = {
    str(BTCUSDT_PERP_BINANCE_ID): lambda: btcusdt_perp_binance(),
}


def instrument_for(symbol: str) -> CryptoPerpetual:
    """由 symbol 字串(InstrumentId 形式)解析 instrument 定義。

    未支援的 symbol 拋 ``ValueError``(應用層約束)。W1 僅 BTCUSDT-PERP.BINANCE。
    """
    factory = _INSTRUMENT_FACTORIES.get(symbol)
    if factory is None:
        raise ValueError(
            f"unsupported symbol {symbol!r}; 支援:{sorted(_INSTRUMENT_FACTORIES)}"
        )
    return factory()


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
