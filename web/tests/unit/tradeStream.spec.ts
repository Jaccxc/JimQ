/**
 * 行為測試:trades channel 端到端視覺路徑(dispatch → market store 形成中 K 線)。
 *
 * 卡 B(Live 次秒 tick):
 * - dispatchMessage 收到 channel='trades' 信封 → 聚合到 market store 形成中那根。
 * - market.applyTick:把每筆成交聚合到最後一根 candle(同 bucket 更新 high/low/close)。
 * - ⛔ 收線權威:applyBar(正式 1m bar)以 bar 為準覆蓋同 time 那根。
 * - trades 不應產生 order/fill/position(純視覺,不碰交易 stores)。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { dispatchMessage } from '@/composables/dispatch'
import { useMarketStore } from '@/stores/market'
import { useFillsStore } from '@/stores/fills'
import { useOrdersStore } from '@/stores/orders'
import type { StreamEnvelope, BarDTO } from '@/types/contract'

const NS = 1_000_000_000

beforeEach(() => setActivePinia(createPinia()))

function bar(time: number, c: number): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(c),
    high: String(c),
    low: String(c),
    close: String(c),
    volume: '0',
  }
}

function tradeEnv(seq: number, time: number, price: string): StreamEnvelope {
  return { channel: 'trades', seq, data: { type: 'TradeTick', time, price } }
}

describe('dispatchMessage trades → market 形成中 K 線', () => {
  it('trades 信封 → market.applyTick(更新最後一根的 high/low/close,不等收線)', () => {
    const market = useMarketStore()
    // 先有一根形成中(收線前)的 1m bar(time 對齊 60s bucket)。
    market.setHistory([bar(1700000040, 40000)])
    dispatchMessage(tradeEnv(1, 1700000050, '40080')) // 同分鐘漲到 40080
    const last = market.bars[market.bars.length - 1]
    expect(last.high).toBe('40080')
    expect(last.close).toBe('40080')
    expect(last.open).toBe('40000') // open 維持
  })

  it('trades 不碰 orders / fills(純視覺)', () => {
    dispatchMessage(tradeEnv(1, 1700000050, '40080'))
    expect(useFillsStore().fills).toHaveLength(0)
    expect(useOrdersStore().orders).toHaveLength(0)
  })
})

describe('market.applyTick / applyBar 收線權威', () => {
  it('tick 聚合後,正式 1m bar 收線以 bar 為準覆蓋同 time 那根', () => {
    const market = useMarketStore()
    market.setHistory([bar(1700000040, 40000)])
    market.applyTick({ time: 1700000050, price: '40123' }) // 視覺跳到 40123
    expect(market.bars[market.bars.length - 1].close).toBe('40123')
    // 正式收線 bar(權威 close=40010)→ 覆蓋。
    market.applyBar(bar(1700000040, 40010))
    const last = market.bars[market.bars.length - 1]
    expect(last.close).toBe('40010') // 以權威 bar 為準
  })

  it('新分鐘 tick → 新增一根形成中 candle(不覆蓋上一根)', () => {
    const market = useMarketStore()
    market.setHistory([bar(1700000040, 40000)])
    market.applyTick({ time: 1700000105, price: '41000' }) // 下一分鐘 bucket
    expect(market.bars).toHaveLength(2)
    expect(market.bars[1].time).toBe(1700000100)
    expect(market.bars[1].open).toBe('41000')
  })
})
