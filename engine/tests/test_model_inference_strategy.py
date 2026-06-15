"""卡 #18 — ModelInferenceStrategy 行為測試(模型輸出驅動下單)。

以**行為**為主,不驗實作細節:用一個假的 ``predict`` 注入製造確定性訊號,
透過小型 BacktestEngine 驗證「模型輸出 → 對應下單」這條 plumbing 通:

- 模型輸出做多訊號 → 進場 bracket(MARKET 進場 + STOP_MARKET SL + LIMIT TP),
  且進場方向為 BUY。
- 模型輸出做空訊號 → 進場方向為 SELL。
- 模型輸出 flat(無訊號)→ 不下任何單。
- 特徵建構復用 ``jimq_core.features``(與 dataset builder 同一份碼);策略對
  模型類型無關 —— 只要物件有 ``predict`` 介面即可(對齊 C8 可插拔)。

不跑真模型;假 predict 直接決定訊號,證明 plumbing 而非 alpha。
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
from jimq_engine.nodes.backtest import build_engine_with_strategy
from jimq_engine.strategies.model_inference import (
    ModelInferenceConfig,
    ModelInferenceStrategy,
)

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


def _bars(prices, instrument):
    return [_bar(i, p, instrument) for i, p in enumerate(prices)]


def _config(**overrides):
    base = dict(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=3,
        slow_period=8,
        trade_size=Decimal("0.100"),
        sl_pct=Decimal("0.01"),
        tp_pct=Decimal("0.02"),
    )
    base.update(overrides)
    return ModelInferenceConfig(**base)


class _FixedSignalModel:
    """假模型:每次 predict 回傳固定訊號,證明 plumbing(非 alpha)。

    任意有 ``predict`` 的物件都能驅動策略(模型類型無關 / C8 可插拔)。
    """

    def __init__(self, signal: int) -> None:
        self.signal = signal

    def predict(self, features):  # noqa: D401 - 介面相容即可
        return self.signal


def test_long_signal_submits_bracket_with_sl_and_tp():
    instrument = btcusdt_perp_binance()
    # 平緩序列即可;訊號由假模型決定,不依賴價格形態。
    bars = _bars([40000.0 + i for i in range(20)], instrument)

    engine = build_engine_with_strategy(
        instrument,
        bars,
        ModelInferenceStrategy(config=_config(), model=_FixedSignalModel(signal=1)),
    )

    orders = engine.cache.orders()
    assert len(orders) >= 3, "做多訊號應送出 bracket(entry + SL + TP)"
    order_types = {o.order_type for o in orders}
    assert OrderType.MARKET in order_types
    assert OrderType.STOP_MARKET in order_types
    assert OrderType.LIMIT in order_types

    positions = engine.cache.positions()
    assert any(p.entry == OrderSide.BUY for p in positions), "做多訊號 → BUY 進場"

    engine.dispose()


def test_short_signal_enters_sell():
    instrument = btcusdt_perp_binance()
    bars = _bars([40000.0 - i for i in range(20)], instrument)

    engine = build_engine_with_strategy(
        instrument,
        bars,
        ModelInferenceStrategy(config=_config(), model=_FixedSignalModel(signal=-1)),
    )

    positions = engine.cache.positions()
    assert len(positions) >= 1, "做空訊號應開出部位"
    assert any(p.entry == OrderSide.SELL for p in positions), "做空訊號 → SELL 進場"

    engine.dispose()


def test_flat_signal_no_orders():
    instrument = btcusdt_perp_binance()
    bars = _bars([40000.0 + i for i in range(20)], instrument)

    engine = build_engine_with_strategy(
        instrument,
        bars,
        ModelInferenceStrategy(config=_config(), model=_FixedSignalModel(signal=0)),
    )

    assert len(engine.cache.orders()) == 0, "無訊號不應下單"

    engine.dispose()


def test_features_reuse_jimq_core_emas():
    """train/serve parity:策略餵給 predict 的特徵 = jimq_core 逐筆 EMA。

    用一個會把收到的特徵記下來的假模型,驗證策略在暖機期(EMA 未 initialized)
    不呼叫 predict,且 initialized 後餵入的特徵就是 jimq_core 的 EMA 值。
    """
    from jimq_core.features import ExponentialMovingAverage

    instrument = btcusdt_perp_binance()
    prices = [40000.0 + (i % 5) * 7 for i in range(20)]
    bars = _bars(prices, instrument)

    captured: list[dict] = []

    class _Recorder:
        def predict(self, features):
            captured.append(dict(features))
            return 0

    engine = build_engine_with_strategy(
        instrument,
        bars,
        ModelInferenceStrategy(config=_config(), model=_Recorder()),
    )

    # 暖機:fast(3) 與 slow(8) 都 initialized 後才該開始 predict。
    # 20 根 - max(period) + 1 次 → 至少呼叫過 predict。
    assert len(captured) > 0, "EMA initialized 後應開始呼叫 predict"

    # 重算 jimq_core 逐筆 EMA,比對最後一次餵入的特徵。
    fast = ExponentialMovingAverage(3)
    slow = ExponentialMovingAverage(8)
    last_fast = last_slow = None
    for c in prices:
        fast.update_raw(c)
        slow.update_raw(c)
        if fast.initialized and slow.initialized:
            last_fast, last_slow = fast.value, slow.value

    feat = captured[-1]
    assert abs(feat["ema_fast"] - last_fast) < 1e-9
    assert abs(feat["ema_slow"] - last_slow) < 1e-9

    engine.dispose()
