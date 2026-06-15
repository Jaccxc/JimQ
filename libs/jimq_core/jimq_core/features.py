"""jimq_core.features — 共用特徵庫(卡 #4)。

反 train/serve skew 的基石:engine Strategy 推論(逐筆增量 ``update_raw``)與
research env 訓練(整批 ``ema_batch``)共用同一份特徵碼,兩者數值必須等價。

EMA 採標準公式:
- alpha = 2 / (period + 1)
- 種子值 = 前 ``period`` 筆的簡單平均(SMA),滿 period 後才 ``initialized``。
- 之後遞推:value = alpha * x + (1 - alpha) * value_prev。

``ExponentialMovingAverage`` 為純 Python、無外部依賴(jimq_core 不依賴
nautilus_trader),故可同時供 engine 策略與 research 環境匯入,消除偏移。
"""

from __future__ import annotations

from typing import Sequence


class ExponentialMovingAverage:
    """逐筆增量更新的指數移動平均。

    用法::

        ema = ExponentialMovingAverage(period=20)
        ema.update_raw(price)      # 每根 bar 餵一次
        if ema.initialized:
            current = ema.value

    與 :func:`ema_batch` 對同一輸入序列產生一致結果(deep module 測試重點)。
    """

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self.alpha = 2.0 / (period + 1)
        self._value: float = 0.0
        self._initialized = False
        self._count = 0
        self._seed_sum = 0.0

    @property
    def value(self) -> float:
        """當前 EMA 值(未 initialized 前為 0.0;請先檢查 ``initialized``)。"""
        return self._value

    @property
    def initialized(self) -> bool:
        """是否已餵滿 ``period`` 筆並完成種子化。"""
        return self._initialized

    def update_raw(self, x: float) -> float:
        """餵入一筆原始值並回傳當前 EMA。

        前 ``period - 1`` 筆只累積種子和;第 ``period`` 筆完成 SMA 種子並
        標記 initialized;其後用標準 alpha 遞推。
        """
        x = float(x)
        if not self._initialized:
            self._count += 1
            self._seed_sum += x
            if self._count == self.period:
                self._value = self._seed_sum / self.period
                self._initialized = True
            return self._value

        self._value = self.alpha * x + (1.0 - self.alpha) * self._value
        return self._value

    def reset(self) -> None:
        """重置為初始狀態(確定性重跑用)。"""
        self._value = 0.0
        self._initialized = False
        self._count = 0
        self._seed_sum = 0.0


def ema_batch(values: Sequence[float], period: int) -> list[float]:
    """整批計算 EMA;回傳 initialized 之後(含種子那筆)的所有 EMA 值。

    與 :class:`ExponentialMovingAverage` 逐筆增量對同一序列等價。回傳長度為
    ``max(0, len(values) - period + 1)``。
    """
    ema = ExponentialMovingAverage(period=period)
    out: list[float] = []
    for v in values:
        ema.update_raw(v)
        if ema.initialized:
            out.append(ema.value)
    return out
