"""jimq_core.timeframes — 共用 timeframe ↔ Nautilus bar 規格映射(卡 #20 W1)。

api(建 run 時推導 bar_type 存進 backtest_run)與 engine command worker(解析
命令時建 BarType / 查 catalog)共用同一份映射,消除兩端 skew。

timeframe 字面值(如 ``1m`` / ``5m`` / ``1h``)→ Nautilus BarType 字串
``{symbol}-{step}-{UNIT}-LAST-EXTERNAL``。純字串處理,無 nautilus 依賴。
"""

from __future__ import annotations

# timeframe 字面值 → (step, Nautilus 聚合 UNIT)。先支援分鐘 / 小時 / 日。
_TIMEFRAME_SPEC: dict[str, tuple[int, str]] = {
    "1m": (1, "MINUTE"),
    "5m": (5, "MINUTE"),
    "15m": (15, "MINUTE"),
    "30m": (30, "MINUTE"),
    "1h": (1, "HOUR"),
    "4h": (4, "HOUR"),
    "1d": (1, "DAY"),
}


def supported_timeframes() -> tuple[str, ...]:
    """回傳支援的 timeframe 字面值(供 web launcher 下拉選單對齊)。"""
    return tuple(_TIMEFRAME_SPEC)


def bar_type_for(symbol: str, timeframe: str) -> str:
    """由 symbol + timeframe 推導 Nautilus BarType 字串。

    例:``bar_type_for("BTCUSDT-PERP.BINANCE", "1m")`` →
    ``"BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"``。

    未支援的 timeframe 拋 ``ValueError``(應用層 enum 約束;鐵律 11 精神)。
    """
    spec = _TIMEFRAME_SPEC.get(timeframe)
    if spec is None:
        raise ValueError(
            f"unsupported timeframe {timeframe!r}; 支援:{sorted(_TIMEFRAME_SPEC)}"
        )
    step, unit = spec
    return f"{symbol}-{step}-{unit}-LAST-EXTERNAL"
