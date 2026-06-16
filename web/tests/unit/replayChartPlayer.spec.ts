/**
 * 行為測試:ReplayChart 接回放引擎 → 換 run / run 完成時把全量資料交給引擎
 * 並自動從頭播放(可暫停),控制列 emit 轉接到引擎方法。
 *
 * mock @/lib/chartController(命令式 sink)與 @/composables/useReplayPlayer
 * (回放引擎),只驗 ReplayChart 對引擎的「行為」(load + play 自動起播、
 * 控制列事件轉接),不驗 LWC 內部或引擎內部。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

const controllerCalls = {
  updateBar: vi.fn(),
  setHistory: vi.fn(),
  setMarkers: vi.fn(),
  setEquityLine: vi.fn(),
  clearEquityLine: vi.fn(),
  reset: vi.fn(),
  fit: vi.fn(),
  destroy: vi.fn(),
  clearPriceLines: vi.fn(),
  addPriceLine: vi.fn(),
}
vi.mock('@/lib/chartController', () => ({
  ChartController: vi.fn().mockImplementation(() => controllerCalls),
}))

const player = {
  currentIndex: ref(0),
  total: ref(0),
  playing: ref(false),
  speed: ref(5),
  load: vi.fn(),
  play: vi.fn(),
  pause: vi.fn(),
  setSpeed: vi.fn(),
  scrub: vi.fn(),
  replay: vi.fn(),
  toEnd: vi.fn(),
  dispose: vi.fn(),
}
vi.mock('@/composables/useReplayPlayer', () => ({
  useReplayPlayer: vi.fn(() => player),
}))

import ReplayChart from '@/components/chart/ReplayChart.vue'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000
function bar(time: number): BarDTO {
  return { ts: time * NS, time, open: '1', high: '2', low: '0', close: '1', volume: '1' }
}

beforeEach(() => {
  for (const fn of Object.values(controllerCalls)) fn.mockClear()
  for (const v of Object.values(player)) {
    if (typeof v === 'object' && v !== null && 'value' in v) continue
    ;(v as ReturnType<typeof vi.fn>).mockClear?.()
  }
  player.total.value = 0
})

describe('ReplayChart 接回放引擎', () => {
  it('掛載且有 bars → load 全量資料給引擎並自動播放', async () => {
    mount(ReplayChart, {
      props: {
        bars: [bar(100), bar(200)],
        markers: [],
        priceLines: [],
        equity: [{ time: 200, value: 10 }],
        replay: true,
      },
    })
    await flushPromises()
    expect(player.load).toHaveBeenCalled()
    const arg = player.load.mock.calls.at(-1)![0]
    expect(arg.bars).toHaveLength(2)
    expect(arg.equity).toHaveLength(1)
    expect(player.play).toHaveBeenCalled()
  })

  it('換 run(bars prop 變)→ 重新 load 並自動從頭播放', async () => {
    const w = mount(ReplayChart, {
      props: { bars: [bar(100)], markers: [], priceLines: [], equity: [], replay: true },
    })
    await flushPromises()
    player.load.mockClear()
    player.play.mockClear()
    await w.setProps({ bars: [bar(300), bar(400)], markers: [], priceLines: [], equity: [], replay: true })
    await flushPromises()
    expect(player.load).toHaveBeenCalled()
    expect(player.load.mock.calls.at(-1)![0].bars).toHaveLength(2)
    expect(player.play).toHaveBeenCalled()
  })

  it('控制列 emit → 轉接到引擎方法', async () => {
    player.total.value = 5
    const w = mount(ReplayChart, {
      props: { bars: [bar(100)], markers: [], priceLines: [], equity: [], replay: true },
    })
    await flushPromises()
    const controls = w.findComponent({ name: 'ReplayControls' })
    expect(controls.exists()).toBe(true)
    controls.vm.$emit('pause')
    controls.vm.$emit('play')
    controls.vm.$emit('set-speed', 20)
    controls.vm.$emit('scrub', 3)
    controls.vm.$emit('replay')
    controls.vm.$emit('to-end')
    await flushPromises()
    expect(player.pause).toHaveBeenCalled()
    expect(player.play).toHaveBeenCalled()
    expect(player.setSpeed).toHaveBeenCalledWith(20)
    expect(player.scrub).toHaveBeenCalledWith(3)
    expect(player.replay).toHaveBeenCalled()
    expect(player.toEnd).toHaveBeenCalled()
  })

  it('空 bars → 不自動播放(load 空,play 不呼叫)', async () => {
    mount(ReplayChart, {
      props: { bars: [], markers: [], priceLines: [], equity: [], replay: true },
    })
    await flushPromises()
    expect(player.play).not.toHaveBeenCalled()
  })
})
