"""卡 #4 — 雙 EMA 交叉策略(bracket OTO 進場 + SL/TP)。

行為:
- 在 ``on_bar`` 維護 fast / slow 兩條 EMA(用 ``jimq_core.features`` 的共用實作,
  消除 train/serve skew —— 與 research 訓練用同一份 EMA 碼)。
- 兩條 EMA 都 initialized 後,偵測交叉:
  - 黃金交叉(fast 由下穿上 slow):做多進場。
  - 死亡交叉(fast 由上穿下 slow):做空進場。
- 進場用 ``OrderFactory.bracket``(OTO):MARKET 進場 + STOP_MARKET 停損 +
  LIMIT 停利,一次送出 order list。SL/TP 由百分比參數決定(簡單即可)。
- 反向交叉時若已有部位,先用 reduce-only MARKET 平倉(連同取消殘留 bracket
  子單),再進反向場(由 ``manage_contingent_orders`` 處理 OCO 殘單)。

確定性:同輸入同結果(EMA 與下單皆為純事件 handler,無亂數)。
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy

from jimq_core.features import ExponentialMovingAverage


class EMACrossConfig(StrategyConfig, frozen=True):
    """雙 EMA 交叉策略設定。

    - ``fast_period`` / ``slow_period``:兩條 EMA 週期(fast < slow)。
    - ``trade_size``:每次進場數量(以 base 幣計,符合 size_precision)。
    - ``sl_pct`` / ``tp_pct``:停損 / 停利距進場價的百分比(小數,如 0.01 = 1%)。
    """

    instrument_id: InstrumentId
    bar_type: BarType
    fast_period: int = 10
    slow_period: int = 20
    trade_size: Decimal = Decimal("0.100")
    sl_pct: Decimal = Decimal("0.01")
    tp_pct: Decimal = Decimal("0.02")


class EMACross(Strategy):
    """雙 EMA 交叉 + bracket(OTO)策略。"""

    def __init__(self, config: EMACrossConfig) -> None:
        super().__init__(config)
        if config.fast_period >= config.slow_period:
            raise ValueError("fast_period must be < slow_period")
        self._fast = ExponentialMovingAverage(config.fast_period)
        self._slow = ExponentialMovingAverage(config.slow_period)
        self.instrument = None
        # 上一根的 fast - slow 正負號,用來偵測交叉(None 表尚未有比較基準)。
        self._prev_diff_positive: bool | None = None

    # ------------------------------------------------------------------ #
    # 生命週期
    # ------------------------------------------------------------------ #
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"instrument {self.config.instrument_id} not found")
            self.stop()
            return
        self.subscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        self._fast.reset()
        self._slow.reset()
        self._prev_diff_positive = None

    # ------------------------------------------------------------------ #
    # 事件
    # ------------------------------------------------------------------ #
    def on_bar(self, bar: Bar) -> None:
        close = bar.close.as_double()
        self._fast.update_raw(close)
        self._slow.update_raw(close)

        if not (self._fast.initialized and self._slow.initialized):
            return

        diff_positive = self._fast.value > self._slow.value

        # 首次兩條皆 initialized:只記基準,不下單(避免把初始狀態當成交叉)。
        if self._prev_diff_positive is None:
            self._prev_diff_positive = diff_positive
            return

        if diff_positive and not self._prev_diff_positive:
            self._on_golden_cross(close)
        elif not diff_positive and self._prev_diff_positive:
            self._on_death_cross(close)

        self._prev_diff_positive = diff_positive

    # ------------------------------------------------------------------ #
    # 交叉處理
    # ------------------------------------------------------------------ #
    def _on_golden_cross(self, ref_price: float) -> None:
        self._close_open_position()
        self._enter_bracket(OrderSide.BUY, ref_price)

    def _on_death_cross(self, ref_price: float) -> None:
        self._close_open_position()
        self._enter_bracket(OrderSide.SELL, ref_price)

    def _close_open_position(self) -> None:
        """若當前 instrument 有淨部位則平倉(反向交叉出場)。"""
        if self.portfolio.is_flat(self.config.instrument_id):
            return
        self.close_all_positions(self.config.instrument_id)

    def _enter_bracket(self, side: OrderSide, ref_price: float) -> None:
        sl_pct = float(self.config.sl_pct)
        tp_pct = float(self.config.tp_pct)
        if side == OrderSide.BUY:
            sl = ref_price * (1.0 - sl_pct)
            tp = ref_price * (1.0 + tp_pct)
        else:
            sl = ref_price * (1.0 + sl_pct)
            tp = ref_price * (1.0 - tp_pct)

        quantity = Quantity(self.config.trade_size, self.instrument.size_precision)
        bracket = self.order_factory.bracket(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=quantity,
            time_in_force=TimeInForce.GTC,
            sl_trigger_price=self.instrument.make_price(sl),
            tp_price=self.instrument.make_price(tp),
        )
        self.submit_order_list(bracket)
