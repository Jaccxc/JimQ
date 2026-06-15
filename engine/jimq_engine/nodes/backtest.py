"""卡 #4 — BacktestEngine 組裝(NETTING + MARGIN + FillModel)。

提供一個確定性的 backtest runner:給 instrument + bars + strategy config,
組好 venue(NETTING OMS、MARGIN account、合理 starting_balances、固定種子的
FillModel),跑完回傳引擎(供取出帳戶/訂單/部位報表)。

確定性:FillModel 給定 ``random_seed`` 後同輸入同結果。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Money
from nautilus_trader.trading.strategy import Strategy

from jimq_engine.strategies.ema_cross import EMACross, EMACrossConfig

BINANCE = Venue("BINANCE")


def default_fill_model(random_seed: int = 42) -> FillModel:
    """固定種子的 FillModel,確保 backtest 確定性可重現。"""
    return FillModel(
        prob_fill_on_limit=0.2,
        prob_slippage=0.0,
        random_seed=random_seed,
    )


def build_engine_with_strategy(
    instrument: Instrument,
    bars: Sequence[Bar],
    strategy: Strategy,
    *,
    starting_usdt: Decimal = Decimal("1_000_000"),
    leverage: Decimal = Decimal("10"),
    random_seed: int = 42,
) -> BacktestEngine:
    """組裝並回傳已 run 完的 BacktestEngine —— 策略類型無關(C8 可插拔)。

    接受任意已實例化的 Nautilus ``Strategy``(規則式 EMA、模型驅動推論策略…),
    組好 venue(NETTING OMS + MARGIN account + USDT 起始餘額 + 固定種子 FillModel)
    後跑完回傳。``build_engine`` 是它對 EMA 策略的便利包裝。
    """
    engine_config = BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        logging=LoggingConfig(bypass_logging=True),
    )
    engine = BacktestEngine(config=engine_config)
    engine.add_venue(
        venue=BINANCE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USDT,
        starting_balances=[Money(starting_usdt, USDT)],
        default_leverage=leverage,
        fill_model=default_fill_model(random_seed),
    )
    engine.add_instrument(instrument)
    engine.add_data(list(bars))
    engine.add_strategy(strategy)
    engine.run()
    return engine


def build_engine(
    instrument: Instrument,
    bars: Sequence[Bar],
    config: EMACrossConfig,
    *,
    starting_usdt: Decimal = Decimal("1_000_000"),
    leverage: Decimal = Decimal("10"),
    random_seed: int = 42,
) -> BacktestEngine:
    """組裝並回傳已 run 完的 BacktestEngine(EMA 策略便利包裝)。

    venue:NETTING OMS + MARGIN account + USDT starting balance + FillModel。
    """
    return build_engine_with_strategy(
        instrument,
        bars,
        EMACross(config=config),
        starting_usdt=starting_usdt,
        leverage=leverage,
        random_seed=random_seed,
    )
