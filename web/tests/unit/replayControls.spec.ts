/**
 * Backtest 回放控制列元件行為測試。
 *
 * ReplayControls 是受控 UI(props 驅動 + emit 事件),不自管回放狀態:
 *  - props:playing / currentIndex / total / speed。
 *  - emit:play / pause / set-speed / scrub / replay / to-end。
 *
 * 只驗互動行為(透過 data-testid 觸發 → emit 正確事件/值),不驗樣式內部。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ReplayControls from '@/components/chart/ReplayControls.vue'

function mountControls(props: Partial<{
  playing: boolean
  currentIndex: number
  total: number
  speed: number
}> = {}) {
  return mount(ReplayControls, {
    props: {
      playing: false,
      currentIndex: 0,
      total: 100,
      speed: 5,
      ...props,
    },
  })
}

describe('ReplayControls 播放/暫停', () => {
  it('未播放時點 ▶ → emit play', async () => {
    const w = mountControls({ playing: false })
    await w.get('[data-testid="replay-playpause"]').trigger('click')
    expect(w.emitted('play')).toHaveLength(1)
    expect(w.emitted('pause')).toBeUndefined()
  })

  it('播放中點 ⏸ → emit pause', async () => {
    const w = mountControls({ playing: true })
    await w.get('[data-testid="replay-playpause"]').trigger('click')
    expect(w.emitted('pause')).toHaveLength(1)
    expect(w.emitted('play')).toBeUndefined()
  })
})

describe('ReplayControls 速度滑桿', () => {
  it('顯示「N 根/秒」label', () => {
    const w = mountControls({ speed: 12 })
    expect(w.get('[data-testid="replay-speed-label"]').text()).toContain('12')
  })

  it('拖速度滑桿 → emit set-speed(數值)', async () => {
    const w = mountControls({ speed: 5 })
    const slider = w.get('[data-testid="replay-speed"]')
    await slider.setValue('20')
    const ev = w.emitted('set-speed')
    expect(ev).toBeTruthy()
    expect(ev!.at(-1)).toEqual([20])
  })

  it('速度滑桿 min=1 max=50', () => {
    const w = mountControls()
    const el = w.get('[data-testid="replay-speed"]').element as HTMLInputElement
    expect(el.min).toBe('1')
    expect(el.max).toBe('50')
  })
})

describe('ReplayControls 進度條(scrub)', () => {
  it('進度條 max = total-1、value = currentIndex', () => {
    const w = mountControls({ currentIndex: 30, total: 100 })
    const el = w.get('[data-testid="replay-progress"]').element as HTMLInputElement
    expect(el.max).toBe('99')
    expect(el.value).toBe('30')
  })

  it('拖進度條 → emit scrub(index)', async () => {
    const w = mountControls({ currentIndex: 0, total: 100 })
    await w.get('[data-testid="replay-progress"]').setValue('42')
    const ev = w.emitted('scrub')
    expect(ev).toBeTruthy()
    expect(ev!.at(-1)).toEqual([42])
  })

  it('顯示 i/total 進度位置', () => {
    const w = mountControls({ currentIndex: 9, total: 100 })
    // 顯示 1-based 的當前/total(10 / 100)。
    expect(w.get('[data-testid="replay-position"]').text()).toContain('100')
  })
})

describe('ReplayControls 重播 / 到結尾', () => {
  it('點 ↺ → emit replay', async () => {
    const w = mountControls()
    await w.get('[data-testid="replay-restart"]').trigger('click')
    expect(w.emitted('replay')).toHaveLength(1)
  })

  it('點 ⏭ → emit to-end', async () => {
    const w = mountControls()
    await w.get('[data-testid="replay-to-end"]').trigger('click')
    expect(w.emitted('to-end')).toHaveLength(1)
  })
})

describe('ReplayControls 空 run 安全', () => {
  it('total=0 時控制列停用(disabled),不爆', () => {
    const w = mountControls({ total: 0, currentIndex: 0 })
    const play = w.get('[data-testid="replay-playpause"]').element as HTMLButtonElement
    expect(play.disabled).toBe(true)
  })
})
