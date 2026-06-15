"""卡 #4 — deep module:jimq_core.features EMA。

反 train/serve skew 的核心:engine 策略推論用「逐筆增量」更新,research 訓練
可能用「整批」計算,兩者必須等價(否則 backtest/live 與訓練特徵不一致)。

測試以行為(public interface)為主:
- EMA 用標準公式 alpha = 2/(period+1) 的數值正確。
- 逐筆增量更新與整批計算同序列必須得到一致結果(關鍵)。
- 未滿 period 前 not initialized;滿 period 後 initialized。
"""

from __future__ import annotations

import math

from jimq_core.features import ExponentialMovingAverage, ema_batch


def _seed_alpha(values, period):
    """純 Python 參考實作:SMA 種子 + 標準 EMA 遞推(供測試對照)。"""
    alpha = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out = [seed]
    for v in values[period:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def test_ema_not_initialized_before_period():
    ema = ExponentialMovingAverage(period=3)
    assert not ema.initialized
    ema.update_raw(1.0)
    ema.update_raw(2.0)
    assert not ema.initialized
    ema.update_raw(3.0)
    assert ema.initialized


def test_ema_seed_is_sma_of_first_period():
    ema = ExponentialMovingAverage(period=3)
    for v in (2.0, 4.0, 6.0):
        ema.update_raw(v)
    # 種子 = 前 period 的 SMA = (2+4+6)/3 = 4.0
    assert math.isclose(ema.value, 4.0, rel_tol=1e-12)


def test_ema_standard_formula_value():
    period = 3
    values = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    ema = ExponentialMovingAverage(period=period)
    for v in values:
        ema.update_raw(v)
    expected = _seed_alpha(values, period)[-1]
    assert math.isclose(ema.value, expected, rel_tol=1e-12)


def test_incremental_equals_batch():
    """逐筆增量 == 整批(train/serve skew 核心保證)。"""
    period = 5
    values = [float(x) for x in (10, 11, 9, 12, 13, 15, 14, 16, 18, 17, 20, 19)]

    ema = ExponentialMovingAverage(period=period)
    incremental = []
    for v in values:
        ema.update_raw(v)
        if ema.initialized:
            incremental.append(ema.value)

    batch = ema_batch(values, period)

    assert len(incremental) == len(batch)
    for a, b in zip(incremental, batch):
        assert math.isclose(a, b, rel_tol=1e-12)


def test_batch_matches_reference():
    period = 4
    values = [float(x) for x in range(1, 20)]
    batch = ema_batch(values, period)
    ref = _seed_alpha(values, period)
    assert len(batch) == len(ref)
    for a, b in zip(batch, ref):
        assert math.isclose(a, b, rel_tol=1e-12)
