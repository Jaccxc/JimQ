/**
 * 卡 #27 (P2-S1) — tabbed shell(AppShell)行為測試。
 *
 * 已拍板 IA:header 含 nav [Live][Backtest][Research] + mode badge
 * (BACKTEST / LIVE-TESTNET)+ 全域 KILL 按鈕(本卡 placeholder/disabled)+
 * WS 狀態。用 vue-router。驗 DOM 行為,不驗實作細節。
 */
import { describe, it, expect, beforeEach } from 'vitest'
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

  it('全域 KILL 按鈕存在且本卡為 disabled(placeholder,真功能待 P2-S3)', () => {
    const w = mountShell()
    const kill = w.get('[data-testid="kill-switch"]')
    expect(kill.text().toUpperCase()).toContain('KILL')
    expect((kill.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('header 含 WS 連線狀態', () => {
    const w = mountShell()
    expect(w.find('[data-testid="conn-status"]').exists()).toBe(true)
  })
})
