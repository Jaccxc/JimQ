"""卡 #18 — 通用模型推論策略(ModelInferenceStrategy)。

這支策略是 research→backtest 迴圈的「serve」端:把**任意訓練好的模型**(只要
物件有 ``predict`` 介面)接上 Nautilus 引擎,在 ``on_bar`` 即時推論並下單。

設計要點(對齊凍結契約):

- **模型類型無關 / C8 可插拔**:策略不知道也不關心模型是 sklearn / torch / RL
  policy。它只呼叫 ``model.predict(features) -> signal``。任何符合此介面的物件都
  能驅動策略(每個權重對應一支獨立 Strategy 的具體實現)。
- **train/serve skew 防線**:``on_bar`` 用 ``jimq_core.features`` 的
  :class:`ExponentialMovingAverage` 逐筆算特徵 —— 與 dataset builder
  (``jimq_research.data.ema_feature``)**同一份碼**。訓練與推論的特徵數值位元等價。
- **確定性**:特徵與下單皆為純事件 handler,無亂數;同輸入同結果。

╔══════════════════════════════════════════════════════════════════════════╗
║  USER REPLACEMENT POINT — 這不是真策略,是你要替換的骨架。                  ║
║                                                                            ║
║  下面兩處是平台的「使用者介面點」,要做真 alpha 時替換,不要改 plumbing:    ║
║                                                                            ║
║  1. _build_features(): 把當前 bar 狀態組成餵給模型的特徵向量/字典。        ║
║     目前只放兩條 EMA(示範)。換成你訓練時用的同一組特徵 —— 並務必繼續走    ║
║     jimq_core.features(或在 dataset builder 與此處共用同一份特徵函式),    ║
║     否則會產生 train/serve skew。                                           ║
║                                                                            ║
║  2. _signal_to_action(): 把 model.predict 的輸出解讀成交易動作。           ║
║     目前約定 signal>0 做多 / signal<0 做空 / 其餘不動(示範)。換成你模型的 ║
║     真正輸出語意(機率閾值、回歸值、RL 離散動作 id …)。                     ║
╚══════════════════════════════════════════════════════════════════════════╝
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


class ModelInferenceConfig(StrategyConfig, frozen=True):
    """通用模型推論策略設定。

    - ``fast_period`` / ``slow_period``:示範特徵(兩條 EMA)的週期。USER
      REPLACEMENT POINT — 換成你模型實際要的特徵設定。
    - ``trade_size``:每次進場數量(base 幣,符合 size_precision)。
    - ``sl_pct`` / ``tp_pct``:停損 / 停利距進場價百分比(小數)。

    注意:模型本身**不**放進 config(Nautilus config 須可序列化;模型權重不應
    塞進序列化字串)。模型物件由 ``__init__(config, model=...)`` 注入。
    """

    instrument_id: InstrumentId
    bar_type: BarType
    fast_period: int = 10
    slow_period: int = 20
    trade_size: Decimal = Decimal("0.100")
    sl_pct: Decimal = Decimal("0.01")
    tp_pct: Decimal = Decimal("0.02")


class ModelInferenceStrategy(Strategy):
    """通用「模型輸出驅動下單」策略(模型類型無關)。

    用法::

        model = load_any_predictable_model(...)   # 有 .predict(features) 即可
        strat = ModelInferenceStrategy(config=cfg, model=model)
        build_engine_with_strategy(instrument, bars, strat)

    每根 bar:更新共用特徵 → 暖機完成後呼叫 ``model.predict`` → 把訊號轉成動作
    (做多 / 做空 bracket 進場 / 不動)。反向訊號先平倉再反手。
    """

    def __init__(self, config: ModelInferenceConfig, *, model) -> None:
        super().__init__(config)
        if config.fast_period >= config.slow_period:
            raise ValueError("fast_period must be < slow_period")
        if not hasattr(model, "predict"):
            raise TypeError("model 必須提供 predict(features) 介面(模型類型無關)")
        # 注入的模型:任何有 predict 的物件(sklearn / torch wrapper / RL policy …)。
        self._model = model
        # 共用特徵(與 dataset builder 同一份 jimq_core.features 碼,反 skew)。
        self._fast = ExponentialMovingAverage(config.fast_period)
        self._slow = ExponentialMovingAverage(config.slow_period)
        self.instrument = None

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

    # ------------------------------------------------------------------ #
    # 事件
    # ------------------------------------------------------------------ #
    def on_bar(self, bar: Bar) -> None:
        close = bar.close.as_double()
        self._fast.update_raw(close)
        self._slow.update_raw(close)

        # 暖機期(任一特徵未 initialized)不推論、不下單。
        if not (self._fast.initialized and self._slow.initialized):
            return

        features = self._build_features(bar)
        signal = self._model.predict(features)
        action = self._signal_to_action(signal)
        if action is not None:
            self._enter(action, close)

    # ------------------------------------------------------------------ #
    # USER REPLACEMENT POINT #1 — 特徵建構
    # ------------------------------------------------------------------ #
    def _build_features(self, bar: Bar) -> dict[str, float]:
        """把當前 bar 狀態組成餵給模型的特徵(示範:兩條共用 EMA)。

        ⚠️ USER REPLACEMENT POINT:換成你訓練時用的同一組特徵。務必繼續走
        ``jimq_core.features``(與 ``jimq_research.data`` 的 dataset builder
        共用同一份特徵碼),否則訓練與推論會 skew。

        回傳純 dict;模型 wrapper 自行決定如何把它轉成自己要的張量/向量。
        """
        return {
            "ema_fast": self._fast.value,
            "ema_slow": self._slow.value,
            "close": bar.close.as_double(),
        }

    # ------------------------------------------------------------------ #
    # USER REPLACEMENT POINT #2 — 訊號語意
    # ------------------------------------------------------------------ #
    def _signal_to_action(self, signal) -> OrderSide | None:
        """把 ``model.predict`` 的輸出解讀成交易動作(示範約定)。

        ⚠️ USER REPLACEMENT POINT:換成你模型輸出的真正語意。目前示範約定:
        - signal > 0 → 做多(BUY)
        - signal < 0 → 做空(SELL)
        - 其餘(0 / None)→ 不動(不下單)

        回傳 ``OrderSide`` 或 ``None``(不動)。
        """
        if signal is None:
            return None
        try:
            value = float(signal)
        except (TypeError, ValueError):
            return None
        if value > 0:
            return OrderSide.BUY
        if value < 0:
            return OrderSide.SELL
        return None

    # ------------------------------------------------------------------ #
    # 下單(plumbing — 一般不需要改)
    # ------------------------------------------------------------------ #
    def _enter(self, side: OrderSide, ref_price: float) -> None:
        """依動作進場:若已有反向部位先平倉,再送 bracket(OTO)。"""
        self._close_open_position()
        self._enter_bracket(side, ref_price)

    def _close_open_position(self) -> None:
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
