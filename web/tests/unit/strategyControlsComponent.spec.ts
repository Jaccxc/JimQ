/**
 * 卡 #24 (W5) — Live 頁 Strategy 控制列(StrategyControls.vue)行為測試。
 *
 * 驗 DOM 行為:Start / Stop 按鈕點擊 → 經注入的 control api 發對應命令;
 * 狀態回饋顯示最近命令。不驗實作細節。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import StrategyControls from '@/components/controls/StrategyControls.vue'

beforeEach(() => setActivePinia(createPinia()))

function mountWith(api: Record<string, unknown>, strategyId = 'ema_cross') {
  return mount(StrategyControls, {
    props: { strategyId },
    global: { provide: { strategyControlApi: api } },
  })
}

describe('StrategyControls', () => {
  it('Start 按鈕點擊發 start 命令給目標策略', async () => {
    const startStrategy = vi.fn().mockResolvedValue({
      strategy_id: 'ema_cross',
      command_type: 'START_STRATEGY',
      correlation_id: 'c1',
    })
    const w = mountWith({ startStrategy })
    await w.get('[data-testid="strategy-start"]').trigger('click')
    expect(startStrategy).toHaveBeenCalledWith('ema_cross', {})
  })

  it('Stop 按鈕點擊發 stop 命令給目標策略', async () => {
    const stopStrategy = vi.fn().mockResolvedValue({
      strategy_id: 'ema_cross',
      command_type: 'STOP_STRATEGY',
      correlation_id: 'c2',
    })
    const w = mountWith({ stopStrategy })
    await w.get('[data-testid="strategy-stop"]').trigger('click')
    expect(stopStrategy).toHaveBeenCalledWith('ema_cross')
  })

  it('送出後顯示最近命令狀態', async () => {
    const startStrategy = vi.fn().mockResolvedValue({
      strategy_id: 'ema_cross',
      command_type: 'START_STRATEGY',
      correlation_id: 'c1',
    })
    const w = mountWith({ startStrategy })
    await w.get('[data-testid="strategy-start"]').trigger('click')
    await w.vm.$nextTick()
    expect(w.get('[data-testid="strategy-status"]').text()).toContain('START_STRATEGY')
  })
})
