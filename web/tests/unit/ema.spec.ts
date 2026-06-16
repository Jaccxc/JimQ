/**
 * 行為測試:emaBatch / emaLineData — 前端 EMA 指標計算。
 *
 * 與 libs/jimq_core/jimq_core/features.py 的 ema_batch 同概念(消除 train/serve skew):
 * - alpha = 2 / (period + 1)
 * - 種子 = 前 period 筆的 SMA,滿 period 才 initialized
 * - 之後遞推 value = alpha*x + (1-alpha)*value_prev
 * 回傳長度 = max(0, len - period + 1)(僅 initialized 之後,含種子那筆)。
 */
import { describe, it, expect } from 'vitest'
import { emaBatch, emaLineData } from '@/lib/ema'
import type { BarDTO } from '@/types/contract'

describe('emaBatch', () => {
  it('回傳長度為 max(0, n - period + 1)', () => {
    expect(emaBatch([1, 2, 3, 4, 5], 3)).toHaveLength(3)
    expect(emaBatch([1, 2], 3)).toHaveLength(0)
    expect(emaBatch([], 3)).toHaveLength(0)
  })

  it('種子為前 period 筆的 SMA', () => {
    // 前三筆 [2,4,6] SMA = 4 → 第一個輸出。
    const out = emaBatch([2, 4, 6, 8], 3)
    expect(out[0]).toBeCloseTo(4, 10)
  })

  it('滿 period 後以標準 alpha 遞推', () => {
    // period=2 → alpha = 2/3。種子 SMA([1,2]) = 1.5;下一筆 x=3 →
    // 2/3*3 + 1/3*1.5 = 2 + 0.5 = 2.5。
    const out = emaBatch([1, 2, 3], 2)
    expect(out[0]).toBeCloseTo(1.5, 10)
    expect(out[1]).toBeCloseTo(2.5, 10)
  })

  it('period=1 等同原序列', () => {
    expect(emaBatch([5, 6, 7], 1)).toEqual([5, 6, 7])
  })
})

const NS = 1_000_000_000
function bar(time: number, close: number): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(close),
    high: String(close),
    low: String(close),
    close: String(close),
    volume: '1',
  }
}

describe('emaLineData', () => {
  it('以 bars 的 close 算 EMA,並對齊到「種子那根起」的 bar time', () => {
    const bars = [bar(100, 2), bar(160, 4), bar(220, 6), bar(280, 8)]
    const line = emaLineData(bars, 3)
    // 長度 = 4 - 3 + 1 = 2。
    expect(line).toHaveLength(2)
    // 第一點對齊第三根 bar(index period-1 = 2)的 time。
    expect(line[0].time).toBe(220)
    expect(line[0].value).toBeCloseTo(4, 10) // SMA([2,4,6])
    expect(line[1].time).toBe(280)
  })

  it('bars 數量不足 period 時回空陣列', () => {
    expect(emaLineData([bar(100, 2), bar(160, 4)], 3)).toEqual([])
  })
})
