"""卡 #29 (P2-S3) — 風控**真實攔截行為**:超名目單被 Nautilus RiskEngine DENIED。

不連網(backtest 引擎)驗證用的是 Nautilus 原生 RiskEngine,而非自造平行風控:
- 用 ``build_engine_with_strategy(..., risk_engine=RiskEngineConfig(max_notional_per_order=...))``
  把與 live 節點**同一個 config 欄位**的名目上限掛進 backtest 引擎。
- 一個極簡測試策略在第一根 bar 送出一筆 LIMIT 單(帶明確價,使 RiskEngine 以
  ``order.price`` 算名目,無需 quote/trade tick → 完全確定性)。
- 斷言**超名目**單被引擎發出 ``OrderDenied`` 事件(reason 含 NOTIONAL),且無成交
  (單根本沒送到 venue);對照組:**限內**單不被 deny。

⚠️ 重要(卡 #29 設計記錄,影響 live 節點):nautilus_trader 1.228.0 的 RiskEngine
``_check_orders_risk_for_account`` 對 **MARGIN 帳戶 early-return**(原碼註解
"TODO: Determine risk controls for margin"),故 ``max_notional_per_order`` 目前**只對
CASH 帳戶**強制執行。又 ``CryptoPerpetual``(BTCUSDT-**PERP**)只能掛 MARGIN 帳戶,
因此本名目上限在 live 期貨節點上**尚不會被 Nautilus 攔截**(forward-compatible:
Nautilus 補上 margin 名目風控即自動生效,因我們已掛好同一 config 欄位)。

本測試因此用 **spot CurrencyPair(BTCUSDT)+ CASH 帳戶**證明 native RiskEngine 確會
deny 超名目單(同一 ``max_notional_per_order`` 接線路徑),不自造平行風控。
live 期貨節點上「對所有帳戶即時生效」的 native 風控是 ``max_order_submit_rate``
(throttler,見 test_live_trade_risk.py)與 kill switch(見 test_control_worker.py)。
runbook 模式 C 已註明此限制與已生效的風控。
"""

from __future__ import annotations

from nautilus_trader.config import RiskEngineConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OrderSide, OrderStatus
from nautilus_trader.model.events import OrderDenied
from nautilus_trader.model.objects import Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

from jimq_engine.nodes.backtest import build_engine_with_strategy

_BASE_NS = 1_700_000_000_000_000_000


def _spot_instrument():
    """spot CurrencyPair(BTCUSDT.BINANCE)—CASH 帳戶可掛(perp 只能掛 margin)。"""
    return TestInstrumentProvider.btcusdt_binance()


def _spot_bars(instrument, n: int = 5, price: float = 40000.0) -> list[Bar]:
    bt = BarType.from_str(f"{instrument.id}-1-MINUTE-LAST-EXTERNAL")
    bars = []
    for i in range(n):
        ts = _BASE_NS + i * 60_000_000_000
        bars.append(
            Bar(
                bt,
                instrument.make_price(price),
                instrument.make_price(price + 5),
                instrument.make_price(price - 5),
                instrument.make_price(price),
                instrument.make_qty(10),
                ts,
                ts,
            )
        )
    return bars


class _OneShotOrderConfig(StrategyConfig, frozen=True):
    instrument_id: str
    bar_type: str
    trade_size: str
    limit_price: str


class _OneShotOrderStrategy(Strategy):
    """第一根 bar 送一筆指定大小+價格的 LIMIT 單後就不再下單(用於驗風控攔截)。"""

    def __init__(self, config: _OneShotOrderConfig) -> None:
        super().__init__(config)
        self._fired = False
        self.instrument = None

    def on_start(self) -> None:
        from nautilus_trader.model.identifiers import InstrumentId

        self.instrument = self.cache.instrument(
            InstrumentId.from_str(self.config.instrument_id)
        )
        self.subscribe_bars(BarType.from_str(self.config.bar_type))

    def on_bar(self, bar: Bar) -> None:
        if self._fired:
            return
        self._fired = True
        qty = Quantity.from_str(self.config.trade_size)
        order = self.order_factory.limit(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=qty,
            price=self.instrument.make_price(float(self.config.limit_price)),
        )
        self.submit_order(order)


def _run(trade_size: str, max_notional: int, limit_price: str = "40000"):
    instrument = _spot_instrument()
    bars = _spot_bars(instrument)
    cfg = _OneShotOrderConfig(
        instrument_id=str(instrument.id),
        bar_type=f"{instrument.id}-1-MINUTE-LAST-EXTERNAL",
        trade_size=trade_size,
        limit_price=limit_price,
    )
    strategy = _OneShotOrderStrategy(config=cfg)
    risk = RiskEngineConfig(
        bypass=False,
        max_notional_per_order={str(instrument.id): max_notional},
    )
    # CASH 帳戶:Nautilus 1.228 名目風控對 margin 尚未實作(見模組 docstring)。
    return build_engine_with_strategy(
        instrument, bars, strategy, risk_engine=risk, account_type=AccountType.CASH
    )


def test_oversized_order_is_denied_by_risk_engine():
    """1.0 BTC @ 40000 = 40000 USDT 名目 > 200 上限 → RiskEngine DENIED,不送 venue。"""
    engine = _run(trade_size="1.000000", max_notional=200)
    orders = engine.cache.orders()
    assert orders, "策略應送出一筆單"
    order = orders[0]
    assert order.status == OrderStatus.DENIED, f"應 DENIED,實際 {order.status}"
    denied = [e for e in order.events if isinstance(e, OrderDenied)]
    assert denied, "應有 OrderDenied 事件"
    assert "NOTIONAL" in denied[0].reason.upper(), denied[0].reason
    # ⛔ 沒送到 venue → 無成交。
    assert order.filled_qty == Quantity.from_int(0)
    engine.dispose()


def test_within_limit_order_not_denied():
    """對照組:0.001 BTC @ 40000 = 40 USDT < 200 上限 → 不被 deny。"""
    engine = _run(trade_size="0.001000", max_notional=200)
    orders = engine.cache.orders()
    assert orders
    order = orders[0]
    assert order.status != OrderStatus.DENIED, "限內單不應被 deny"
    engine.dispose()
