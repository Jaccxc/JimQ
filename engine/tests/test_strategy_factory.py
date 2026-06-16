"""卡 #20 (W1) — 策略 factory by name(engine.control.factory)。

行為層測試(public interface):
- ``build_strategy_config(name, instrument_id, bar_type, params)`` 依策略名建
  對應的 Nautilus StrategyConfig;``ema_cross`` 先行,params 映射到 EMACrossConfig
  欄位(fast_period/slow_period/...);未知名拋 ``ValueError``(預留擴充)。
- ``known_strategies()`` 列出已註冊策略名(供 web launcher 對齊)。
"""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from jimq_engine.control.factory import build_strategy_config, known_strategies
from jimq_engine.strategies.ema_cross import EMACrossConfig

_IID = "BTCUSDT-PERP.BINANCE"
_BT = "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"


def test_ema_cross_registered():
    assert "ema_cross" in known_strategies()


def test_build_ema_cross_config_maps_params():
    cfg = build_strategy_config(
        "ema_cross",
        instrument_id=_IID,
        bar_type=_BT,
        params={"fast_period": 3, "slow_period": 8},
    )
    assert isinstance(cfg, EMACrossConfig)
    assert cfg.fast_period == 3
    assert cfg.slow_period == 8
    assert cfg.instrument_id == InstrumentId.from_str(_IID)
    assert cfg.bar_type == BarType.from_str(_BT)


def test_build_ema_cross_uses_defaults_when_params_absent():
    cfg = build_strategy_config(
        "ema_cross", instrument_id=_IID, bar_type=_BT, params={}
    )
    assert isinstance(cfg, EMACrossConfig)
    # EMACrossConfig 預設 fast<slow,合法。
    assert cfg.fast_period < cfg.slow_period


def test_build_ema_cross_accepts_decimal_params():
    cfg = build_strategy_config(
        "ema_cross",
        instrument_id=_IID,
        bar_type=_BT,
        params={"fast_period": 5, "slow_period": 20, "trade_size": "0.250"},
    )
    assert cfg.trade_size == Decimal("0.250")


def test_unknown_strategy_raises():
    import pytest

    with pytest.raises(ValueError):
        build_strategy_config(
            "does_not_exist", instrument_id=_IID, bar_type=_BT, params={}
        )
