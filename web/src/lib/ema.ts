/**
 * 前端 EMA 指標計算(與 libs/jimq_core/jimq_core/features.py 的 ema_batch 同概念)。
 *
 * 反 train/serve skew:engine 策略 / research 訓練用 jimq_core.ExponentialMovingAverage,
 * 前端圖表疊圖用同一份標準公式,數值等價。
 * - alpha = 2 / (period + 1)
 * - 種子值 = 前 period 筆的簡單平均(SMA),滿 period 後才 initialized。
 * - 之後遞推:value = alpha * x + (1 - alpha) * value_prev。
 *
 * emaBatch 回傳 initialized 之後(含種子那筆)的所有 EMA 值,
 * 長度 = max(0, len - period + 1)。
 */
import type { BarDTO } from '@/types/contract'
import type { Time, UTCTimestamp } from 'lightweight-charts'

/** LWC line series 單點。 */
export interface LinePoint {
  time: Time
  value: number
}

/**
 * 整批計算 EMA。對齊 jimq_core.ema_batch:回傳長度 max(0, len - period + 1),
 * 僅含 initialized 之後(含種子那筆)的值。
 */
export function emaBatch(values: number[], period: number): number[] {
  if (period < 1) throw new Error('period must be >= 1')
  const out: number[] = []
  const alpha = 2 / (period + 1)
  let value = 0
  let initialized = false
  let seedSum = 0
  for (let i = 0; i < values.length; i++) {
    const x = values[i]
    if (!initialized) {
      seedSum += x
      if (i + 1 === period) {
        value = seedSum / period
        initialized = true
        out.push(value)
      }
    } else {
      value = alpha * x + (1 - alpha) * value
      out.push(value)
    }
  }
  return out
}

/**
 * 由 bars 的 close 計算 EMA line series 資料。
 * 對齊到「種子那根」起的 bar time(第 i 個輸出對齊第 (period-1+i) 根 bar)。
 */
export function emaLineData(bars: BarDTO[], period: number): LinePoint[] {
  if (bars.length < period) return []
  const closes = bars.map((b) => Number(b.close))
  const ema = emaBatch(closes, period)
  const offset = period - 1
  return ema.map((value, i) => ({
    time: bars[offset + i].time as UTCTimestamp,
    value,
  }))
}
