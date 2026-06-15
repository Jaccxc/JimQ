"""純函式:raw Binance REST 資料 → Nautilus 物件(卡 #3)。

不做任何 I/O —— 輸入是已抓回的 list,輸出是 Nautilus 物件。
精度由傳入的 instrument 決定,確保與 catalog/instrument 定義一致。
所有時間戳由 Binance 毫秒轉奈秒(×1_000_000)。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from nautilus_trader.model.data import Bar, BarType, FundingRateUpdate
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Price, Quantity

_MS_TO_NS = 1_000_000


def klines_to_bars(
    raw_klines: Sequence[Sequence],
    bar_type: BarType,
    instrument: Instrument,
) -> list[Bar]:
    """把 Binance USD-M klines 陣列轉成 Nautilus ``Bar`` 物件。

    Binance kline 單筆格式:
    ``[openTime(ms), open, high, low, close, volume, closeTime(ms), ...]``

    - OHLC 用 instrument.price_precision 建 ``Price``。
    - volume 用 instrument.size_precision 建 ``Quantity``。
    - ts_event / ts_init 用 openTime(ms→ns)。
    - 結果依 ts_init 升冪排序(catalog 寫入要求單調遞增)。
    """
    price_prec = instrument.price_precision
    size_prec = instrument.size_precision

    bars: list[Bar] = []
    for k in raw_klines:
        ts = int(k[0]) * _MS_TO_NS
        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price(float(k[1]), price_prec),
                high=Price(float(k[2]), price_prec),
                low=Price(float(k[3]), price_prec),
                close=Price(float(k[4]), price_prec),
                volume=Quantity(float(k[5]), size_prec),
                ts_event=ts,
                ts_init=ts,
            )
        )
    bars.sort(key=lambda b: b.ts_init)
    return bars


def funding_history_to_updates(
    raw_funding: Sequence[dict],
    instrument_id: InstrumentId,
) -> list[FundingRateUpdate]:
    """把 Binance funding rate history 轉成 ``FundingRateUpdate`` 物件。

    Binance 單筆格式:``{"symbol", "fundingTime"(ms), "fundingRate", "markPrice"}``。
    rate 用 ``Decimal`` 保留精度;ts_event/ts_init 用 fundingTime(ms→ns)。
    結果依 ts_init 升冪排序。
    """
    updates: list[FundingRateUpdate] = []
    for f in raw_funding:
        ts = int(f["fundingTime"]) * _MS_TO_NS
        updates.append(
            FundingRateUpdate(
                instrument_id=instrument_id,
                rate=Decimal(str(f["fundingRate"])),
                ts_event=ts,
                ts_init=ts,
            )
        )
    updates.sort(key=lambda u: u.ts_init)
    return updates
