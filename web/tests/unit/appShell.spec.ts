/**
 * 卡 #27 (P2-S1) — tabbed shell(AppShell)行為測試。
 *
 * 已拍板 IA:header 含 nav [Live][Backtest][Research] + mode badge
 * (BACKTEST / LIVE-TESTNET)+ 全域 KILL 按鈕(本卡 placeholder/disabled)+
 * WS 狀態。用 vue-router。驗 DOM 行為,不驗實作細節。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, RouterLinkStub } from '@vue/test-utils'
import AppShell from '@/components/AppShell.vue'
import { useAppModeStore } from '@/stores/appMode'

beforeEach(() => setActivePinia(createPinia()))

function mountShell() {
  return mount(AppShell, {
    global: {
      stubs: { RouterLink: RouterLinkStub, RouterView: true },
    },
  })
}

describe('AppShell tabbed header', () => {
  it('nav 有 Live / Backtest / Research 三個分頁籤', () => {
    const w = mountShell()
    const links = w.findAllComponents(RouterLinkStub)
    const targets = links.map((l) => l.props('to'))
    expect(targets).toContain('/live')
    expect(targets).toContain('/backtest')
    expect(targets).toContain('/research')
  })

  it('header 顯示 mode badge,預設 BACKTEST', () => {
    const w = mountShell()
    const badge = w.get('[data-testid="mode-badge"]')
    expect(badge.text()).toContain('BACKTEST')
  })

  it('mode badge 在 LIVE-TESTNET 模式顯示 LIVE-TESTNET', async () => {
    const w = mountShell()
    useAppModeStore().setLive()
    await w.vm.$nextTick()
    const badge = w.get('[data-testid="mode-badge"]')
    expect(badge.text()).toContain('LIVE-TESTNET')
  })

  it('全域 KILL 按鈕存在且已啟用(卡 #24 W5:接命令平面真功能)', () => {
    const w = mountShell()
    const kill = w.get('[data-testid="kill-switch"]')
    expect(kill.text().toUpperCase()).toContain('KILL')
    // 卡 #24:從 disabled placeholder 變真功能 → 不再 disabled。
    expect((kill.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('點全域 KILL 發 KILL 命令(經注入的 control composable)', async () => {
    const killAll = vi.fn().mockResolvedValue({
      strategy_id: null,
      command_type: 'KILL',
      correlation_id: 'c-kill',
    })
    const w = mount(AppShell, {
      global: {
        stubs: { RouterLink: RouterLinkStub, RouterView: true },
        provide: { strategyControlApi: { killAll } },
      },
    })
    await w.get('[data-testid="kill-switch"]').trigger('click')
    expect(killAll).toHaveBeenCalled()
  })

  it('header 含 WS 連線狀態', () => {
    const w = mountShell()
    expect(w.find('[data-testid="conn-status"]').exists()).toBe(true)
  })
})
