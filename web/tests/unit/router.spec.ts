/**
 * 卡 #27 (P2-S1) — router 行為:三分頁路由 + 根重導向到 /live。
 */
import { describe, it, expect } from 'vitest'
import { router } from '@/router'

function names() {
  return router.getRoutes().map((r) => r.path)
}

describe('router', () => {
  it('有 /live /backtest /research 路由', () => {
    const paths = names()
    expect(paths).toContain('/live')
    expect(paths).toContain('/backtest')
    expect(paths).toContain('/research')
  })

  it('根路徑 / 重導向到 /live', async () => {
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/live')
  })

  it('/backtest 解析到 backtest 路由', async () => {
    await router.push('/backtest')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/backtest')
  })
})
