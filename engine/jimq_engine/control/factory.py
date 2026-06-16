"""卡 #20 (W1) — 策略 factory by name(命令平面用)。

command worker 收到 run_backtest 命令時,依命令的 ``strategy`` 名 + ``params``
建對應的 Nautilus ``StrategyConfig``。``ema_cross`` 先行,介面預留擴充(W2–W5
與後續模型驅動策略掛同一 registry)。

設計:
- registry 是 ``name -> builder`` 映射;builder 把使用者 params(JSON 友善的
  純量 / 字串)映射成該策略 config 的型別(Decimal / int)。
- 未知策略名拋 ``ValueError``(應用層約束;命令來源不可信)。
- 此處只建 **config**;worker 再用 ``build_streaming_engine`` 把 config 實例化成
  策略並跑(關注點分離,利測試)。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from jimq_engine.strategies.ema_cross import EMACrossConfig


def _build_ema_cross(
    instrument_id: InstrumentId, bar_type: BarType, params: dict[str, Any]
) -> EMACrossConfig:
    """params -> EMACrossConfig。缺省欄位用 EMACrossConfig 預設值。"""
    kwargs: dict[str, Any] = {"instrument_id": instrument_id, "bar_type": bar_type}
    if "fast_period" in params:
        kwargs["fast_period"] = int(params["fast_period"])
    if "slow_period" in params:
        kwargs["slow_period"] = int(params["slow_period"])
    for dec_field in ("trade_size", "sl_pct", "tp_pct"):
        if dec_field in params:
            kwargs[dec_field] = Decimal(str(params[dec_field]))
    return EMACrossConfig(**kwargs)


# 策略名 -> config builder。新增策略在此註冊(預留 W2–W5 / 模型驅動策略)。
_REGISTRY: dict[str, Callable[[InstrumentId, BarType, dict[str, Any]], StrategyConfig]] = {
    "ema_cross": _build_ema_cross,
}


def known_strategies() -> tuple[str, ...]:
    """回傳已註冊策略名(供 web launcher 下拉對齊)。"""
    return tuple(_REGISTRY)


def build_strategy_config(
    name: str,
    *,
    instrument_id: str | InstrumentId,
    bar_type: str | BarType,
    params: dict[str, Any],
) -> StrategyConfig:
    """依策略名建對應的 Nautilus ``StrategyConfig``。未知名拋 ``ValueError``。"""
    builder = _REGISTRY.get(name)
    if builder is None:
        raise ValueError(f"unknown strategy {name!r}; 已註冊:{sorted(_REGISTRY)}")
    iid = instrument_id if isinstance(instrument_id, InstrumentId) else InstrumentId.from_str(instrument_id)
    bt = bar_type if isinstance(bar_type, BarType) else BarType.from_str(bar_type)
    return builder(iid, bt, params)
