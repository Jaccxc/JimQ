/**
 * 回放播放器 — 行為測試:ReplayChart 接 equity prop → 回放引擎驅動命令式
 * 畫權益副圖,且換 run(props 變)時重新 load(reset 隔離舊 run)並從頭回放;
 * 「跳結尾顯示完整」(toEnd)時權益副圖以全量重畫,equity 空時 clearEquityLine。
 *
 * 透過 mock @/lib/chartController 攔截命令式呼叫,使用真實 useReplayPlayer,
 * 只驗 ReplayChart→引擎→controller 的整體行為(不驗 LWC 內部)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// 攔截 ChartController:記錄命令式呼叫(含回放引擎用的 updateBar/reset/fit)。
const calls = {
  updateBar: vi.fn(),
  setHistory: vi.fn(),
  setMarkers: vi.fn(),
  clearPriceLines: vi.fn(),
  addPriceLine: vi.fn(),
  setEquityLine: vi.fn(),
  clearEquityLine: vi.fn(),
  reset: vi.fn(),
  fit: vi.fn(),
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

/** 找控制列並觸發「跳到結尾」→ 引擎一次性畫完整。 */
async function clickToEnd(w: ReturnType<typeof mount>) {
  await w.get('[data-testid="replay-to-end"]').trigger('click')
  await flushPromises()
}

describe('ReplayChart 權益副圖(回放)', () => {
  it('掛載時 reset 隔離後逐根回放;跳結尾 → setEquityLine 全量', async () => {
    const equity = [
      { time: 100, value: 10 },
      { time: 200, value: 25 },
    ]
    const w = mount(ReplayChart, {
      props: { bars: [bar(100, 1), bar(200, 2)], markers: [], priceLines: [], equity, replay: true },
    })
    await flushPromises()
    // load 先 reset(隔離舊 run);逐根 append 至少畫第 0 根。
    expect(calls.reset).toHaveBeenCalled()
    expect(calls.updateBar).toHaveBeenCalled()
    // 跳結尾顯示完整 → 權益副圖以全量重畫。
    await clickToEnd(w)
    expect(calls.setEquityLine).toHaveBeenLastCalledWith(equity)
  })

  it('換 run(equity prop 變)→ 重新 load(reset)後跳結尾以新資料全量重畫', async () => {
    const w = mount(ReplayChart, {
      props: {
        bars: [bar(100, 1)],
        markers: [],
        priceLines: [],
        equity: [{ time: 100, value: 10 }],
        replay: true,
      },
    })
    await flushPromises()
    calls.reset.mockClear()
    const next = [{ time: 300, value: 99 }]
    await w.setProps({ bars: [bar(300, 2)], markers: [], priceLines: [], equity: next, replay: true })
    await flushPromises()
    // 換 run → 重新 load(reset 隔離舊 run 曲線)。
    expect(calls.reset).toHaveBeenCalled()
    await clickToEnd(w)
    expect(calls.setEquityLine).toHaveBeenLastCalledWith(next)
  })

  it('equity 空 → 回放與跳結尾都 clearEquityLine(不殘留前一 run 曲線)', async () => {
    const w = mount(ReplayChart, {
      props: {
        bars: [bar(100, 1)],
        markers: [],
        priceLines: [],
        equity: [{ time: 100, value: 10 }],
        replay: true,
      },
    })
    await w.setProps({ bars: [bar(100, 1)], markers: [], priceLines: [], equity: [], replay: true })
    await flushPromises()
    await clickToEnd(w)
    expect(calls.clearEquityLine).toHaveBeenCalled()
  })
})
