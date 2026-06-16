/**
 * 卡 C — 行為測試:ReplayChart 接 equity prop → 命令式畫權益副圖,
 * 且換 run(props 變)時整體重畫(主圖 setHistory + setMarkers 全量替換 +
 * 權益副圖 setEquityLine 重畫;equity 空時 clearEquityLine)。
 *
 * 透過 mock @/lib/chartController 攔截命令式呼叫,只驗 ReplayChart 對
 * controller 的行為(不驗 LWC 內部)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// 攔截 ChartController:記錄每個實例的命令式呼叫。
const calls = {
  setHistory: vi.fn(),
  setMarkers: vi.fn(),
  clearPriceLines: vi.fn(),
  addPriceLine: vi.fn(),
  setEquityLine: vi.fn(),
  clearEquityLine: vi.fn(),
  destroy: vi.fn(),
}
vi.mock('@/lib/chartController', () => ({
  ChartController: vi.fn().mockImplementation(() => calls),
}))

import ReplayChart from '@/components/chart/ReplayChart.vue'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000
function bar(time: number, close: number): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(close),
    high: String(close + 1),
    low: String(close - 1),
    close: String(close),
    volume: '1',
  }
}

beforeEach(() => {
  for (const fn of Object.values(calls)) fn.mockClear()
})

describe('ReplayChart 權益副圖', () => {
  it('掛載時以 equity prop 畫權益副圖(setEquityLine)', () => {
    const equity = [
      { time: 100, value: 10 },
      { time: 200, value: 25 },
    ]
    mount(ReplayChart, {
      props: { bars: [bar(100, 1)], markers: [], priceLines: [], equity },
    })
    expect(calls.setEquityLine).toHaveBeenCalledWith(equity)
  })

  it('換 run(equity prop 變)→ 權益副圖以新資料重畫', async () => {
    const w = mount(ReplayChart, {
      props: {
        bars: [bar(100, 1)],
        markers: [],
        priceLines: [],
        equity: [{ time: 100, value: 10 }],
      },
    })
    calls.setEquityLine.mockClear()
    const next = [{ time: 300, value: 99 }]
    await w.setProps({ bars: [bar(300, 2)], markers: [], priceLines: [], equity: next })
    await flushPromises()
    expect(calls.setEquityLine).toHaveBeenLastCalledWith(next)
  })

  it('equity 空 → clearEquityLine(不殘留前一 run 曲線)', async () => {
    const w = mount(ReplayChart, {
      props: {
        bars: [bar(100, 1)],
        markers: [],
        priceLines: [],
        equity: [{ time: 100, value: 10 }],
      },
    })
    await w.setProps({ bars: [], markers: [], priceLines: [], equity: [] })
    await flushPromises()
    expect(calls.clearEquityLine).toHaveBeenCalled()
  })
})
