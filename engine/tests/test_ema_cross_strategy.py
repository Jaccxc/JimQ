"""卡 #4 — 策略行為測試(以行為為主,不驗實作細節)。

用合成 bar 序列製造一次黃金交叉,透過小型 BacktestEngine 驗證:
- 交叉觸發進場下單(有訂單產生)。
- bracket(OTO)同時產生 SL(STOP_MARKET)與 TP(LIMIT)子單。
- 進場 MARKET 成交、開出部位(完整生命週期起點)。

不跑大 backtest;只用足夠製造一次交叉的合成資料。
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide, OrderType
from nautilus_trader.model.objects import Price, Quantity

from jimq_engine.catalog.ingest import BAR_TYPE_1M
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.nodes.backtest import build_engine
from jimq_engine.strategies.ema_cross import EMACrossConfig

_BASE_MS = 1_700_000_000_000
_MS_TO_NS = 1_000_000


def _bar(i: int, price: float, instrument) -> Bar:
    ts = (_BASE_MS + i * 60_000) * _MS_TO_NS
    p = Price(price, instrument.price_precision)
    return Bar(
        bar_type=BAR_TYPE_1M,
        open=p,
        high=Price(price + 5, instrument.price_precision),
        low=Price(price - 5, instrument.price_precision),
        close=p,
        volume=Quantity(10.0, instrument.size_precision),
        ts_event=ts,
        ts_init=ts,
    )


def _golden_cross_prices() -> list[float]:
    """先平緩下行(fast 低於 slow),再強力上行製造黃金交叉。"""
    down = [40000.0 - i * 20 for i in range(15)]   # 緩跌
    up = [down[-1] + i * 120 for i in range(1, 20)]  # 急漲 → fast 上穿 slow
    return down + up


def _make_bars(prices, instrument):
    return [_bar(i, p, instrument) for i, p in enumerate(prices)]


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


def test_golden_cross_submits_bracket_with_sl_and_tp():
    instrument = btcusdt_perp_binance()
    bars = _make_bars(_golden_cross_prices(), instrument)
    engine = build_engine(instrument, bars, _config())

    orders = engine.cache.orders()
    assert len(orders) >= 3, "bracket 應產生 entry + SL + TP 至少 3 張單"

    order_types = {o.order_type for o in orders}
    assert OrderType.MARKET in order_types, "應有 MARKET 進場單"
    assert OrderType.STOP_MARKET in order_types, "bracket 應含 STOP_MARKET 停損子單"
    assert OrderType.LIMIT in order_types, "bracket 應含 LIMIT 停利子單"

    engine.dispose()


def test_golden_cross_opens_position():
    instrument = btcusdt_perp_binance()
    bars = _make_bars(_golden_cross_prices(), instrument)
    engine = build_engine(instrument, bars, _config())

    positions = engine.cache.positions()
    assert len(positions) >= 1, "進場成交後應開出部位"
    # 黃金交叉 → 做多進場(entry order side = BUY)。
    assert any(p.entry == OrderSide.BUY for p in positions)
    # 完整生命週期:bracket SL/TP 觸發出場 → 部位已平。
    assert any(not p.is_open for p in positions)

    engine.dispose()


def test_golden_cross_market_only_when_bracket_disabled():
    """use_bracket=False:交叉只下單純 MARKET 進場(無 OCO 條件子單)。

    Binance USDT-M Futures adapter 不支援 bracket 的 OCO 條件單
    (本地 RiskEngine 直接 OrderDenied UNSUPPORTED_OCO_CONDITIONAL_ORDERS),
    故 live testnet 路徑改下純 MARKET 單 → 可真正送達 venue 成交(round-trip)。
    策略邏輯(交叉偵測)與 backtest 完全共用,只切換下單型態 → parity。
    """
    instrument = btcusdt_perp_binance()
    bars = _make_bars(_golden_cross_prices(), instrument)
    cfg = EMACrossConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=3,
        slow_period=8,
        trade_size=Decimal("0.100"),
        use_bracket=False,
    )
    engine = build_engine(instrument, bars, cfg)

    orders = engine.cache.orders()
    assert orders, "交叉應下進場單"
    order_types = {o.order_type for o in orders}
    # 只允許 MARKET 型態 —— 不得有 OCO 條件子單(STOP_MARKET / LIMIT)。
    assert OrderType.MARKET in order_types
    assert OrderType.STOP_MARKET not in order_types, "純市價單路徑不應有 STOP_MARKET"
    assert OrderType.LIMIT not in order_types, "純市價單路徑不應有 LIMIT 子單"

    positions = engine.cache.positions()
    assert len(positions) >= 1, "市價進場成交後應開出部位(round-trip 起點)"
    assert any(p.entry == OrderSide.BUY for p in positions)

    engine.dispose()


def test_no_cross_no_orders():
    """單調序列(無交叉)不應下任何單。"""
    instrument = btcusdt_perp_binance()
    prices = [40000.0 + i * 50 for i in range(30)]  # 一路上行,fast 始終高於 slow
    bars = _make_bars(prices, instrument)
    engine = build_engine(instrument, bars, _config())

    assert len(engine.cache.orders()) == 0

    engine.dispose()
