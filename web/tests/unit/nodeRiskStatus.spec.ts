/**
 * 卡 #29 (P2-S3) — Live 頁控制列顯示**節點狀態**與**風控摘要**(行為測試)。
 *
 * 驗 DOM 行為(不驗實作細節):
 * - 節點狀態徽章:預設 RUNNING;全域 KILL 後變 KILLED(由 strategyControl store
 *   的 killed 旗標驅動,復用既有 store,不新增端點)。
 * - 風控摘要:顯示生效中的 max notional 與 order rate limit(以 prop 注入,
 *   來源為 live 節點風控 config 預設;讓 operator 看到風控生效中)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import StrategyControls from '@/components/controls/StrategyControls.vue'
import { useStrategyControlStore } from '@/stores/strategyControl'

beforeEach(() => setActivePinia(createPinia()))

function mountWith(props: Record<string, unknown> = {}, api: Record<string, unknown> = {}) {
  return mount(StrategyControls, {
    props,
    global: { provide: { strategyControlApi: api } },
  })
}

describe('StrategyControls 節點/風控狀態', () => {
  it('預設顯示節點狀態 RUNNING', () => {
    const w = mountWith()
    expect(w.get('[data-testid="node-status"]').text()).toContain('RUNNING')
  })

  it('全域 KILL 後節點狀態變 KILLED', async () => {
    const w = mountWith()
    const store = useStrategyControlStore()
    store.recordCommand({ strategy_id: null, command_type: 'KILL', correlation_id: 'k1' })
    await w.vm.$nextTick()
    expect(w.get('[data-testid="node-status"]').text()).toContain('KILLED')
  })

  it('風控摘要顯示生效中的 max notional 與 order rate limit', () => {
    const w = mountWith({ maxNotional: 200, orderRateLimit: '10/00:00:01' })
    const summary = w.get('[data-testid="risk-summary"]').text()
    expect(summary).toContain('200')
    expect(summary).toContain('10/00:00:01')
  })

  it('未提供風控 prop 時用保守預設顯示', () => {
    const w = mountWith()
    const summary = w.get('[data-testid="risk-summary"]').text()
    // 預設名目 200 USDT / 10 單/秒(對齊 live 節點 DEFAULT_MAX_NOTIONAL_USDT)。
    expect(summary).toContain('200')
    expect(summary).toContain('10/00:00:01')
  })
})
