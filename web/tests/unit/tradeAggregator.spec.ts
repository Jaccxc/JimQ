/**
 * 行為測試:tradeAggregator —— 把逐筆成交 TradeTick 聚合到「形成中的那根 1m K 線」。
 *
 * 卡 B(Live 次秒 tick)核心視覺邏輯(純函式,無 Vue / LWC 依賴):
 * - 每筆成交 {time(秒), price} 落入所屬分鐘 bucket(floor(time/60)*60)。
 * - 同 bucket:更新 high=max、low=min、close=最新成交價;open 維持(第一筆的價)。
 * - 新 bucket(新分鐘到來):換一根新的形成中 candle(OHLC 皆 = 第一筆價)。
 * - 比現有 bucket 舊的成交:略過(亂序保護)。
 *
 * ⛔ 純視覺:此函式只算「形成中、尚未收線」那根的 OHLC;正式 1m bar 收線時由
 * bars channel 權威覆蓋(見 market store applyTick / applyBar)。
 */
import { describe, it, expect } from 'vitest'
import { aggregateTick } from '@/lib/tradeAggregator'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000

function bar(time: number, o: number, h: number, l: number, c: number): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(o),
    high: String(h),
    low: String(l),
    close: String(c),
    volume: '0',
  }
}

describe('aggregateTick — 形成中 K 線聚合', () => {
  it('無現有 bar:第一筆成交開出一根形成中 candle(OHLC 皆 = 成交價)', () => {
    const out = aggregateTick(null, { time: 1700000005, price: '40000' })
    expect(out.time).toBe(1699999980) // bucket = floor(1700000005/60)*60
    expect(out.open).toBe('40000')
    expect(out.high).toBe('40000')
    expect(out.low).toBe('40000')
    expect(out.close).toBe('40000')
  })

  it('同分鐘 bucket:更新 high/low/close,open 維持(不等收線)', () => {
    const bucket = 1700000040 // 已對齊 60s
    let forming = bar(bucket, 40000, 40000, 40000, 40000)
    forming = aggregateTick(forming, { time: bucket + 10, price: '40050' }) // 漲
    expect(forming.high).toBe('40050')
    expect(forming.close).toBe('40050')
    expect(forming.open).toBe('40000') // open 不變
    expect(forming.low).toBe('40000')

    forming = aggregateTick(forming, { time: bucket + 20, price: '39950' }) // 跌破
    expect(forming.low).toBe('39950')
    expect(forming.close).toBe('39950')
    expect(forming.high).toBe('40050') // high 維持
    expect(forming.open).toBe('40000')
  })

  it('新分鐘到來:換一根新的形成中 candle', () => {
    const bucket = 1700000040
    const forming = bar(bucket, 40000, 40080, 39900, 40010)
    const next = aggregateTick(forming, { time: bucket + 60, price: '40010' })
    expect(next.time).toBe(bucket + 60) // 新 bucket
    expect(next.open).toBe('40010')
    expect(next.high).toBe('40010')
    expect(next.low).toBe('40010')
    expect(next.close).toBe('40010')
  })

  it('比現有 bucket 舊的成交 → 略過(回傳原 candle 不變)', () => {
    const bucket = 1700000120
    const forming = bar(bucket, 41000, 41000, 41000, 41000)
    const out = aggregateTick(forming, { time: bucket - 30, price: '99999' })
    expect(out).toEqual(forming) // 不動
  })

  it('bucketSeconds 可配置(如 5m = 300s)', () => {
    const out = aggregateTick(null, { time: 1700000123, price: '40000' }, 300)
    expect(out.time).toBe(Math.floor(1700000123 / 300) * 300)
  })
})
