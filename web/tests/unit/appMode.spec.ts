/**
 * 卡 #27 (P2-S1) — appMode store 行為測試。
 *
 * mode badge 依資料來源:預設 BACKTEST;live 節點在跑時切 LIVE-TESTNET。
 * 只驗 public state/action 行為。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppModeStore } from '@/stores/appMode'

beforeEach(() => setActivePinia(createPinia()))

describe('appMode store', () => {
  it('預設 mode = BACKTEST', () => {
    const s = useAppModeStore()
    expect(s.mode).toBe('BACKTEST')
    expect(s.badgeLabel).toBe('BACKTEST')
  })

  it('setLive 切到 LIVE-TESTNET', () => {
    const s = useAppModeStore()
    s.setLive()
    expect(s.mode).toBe('LIVE-TESTNET')
    expect(s.badgeLabel).toBe('LIVE-TESTNET')
  })

  it('setBacktest 切回 BACKTEST', () => {
    const s = useAppModeStore()
    s.setLive()
    s.setBacktest()
    expect(s.mode).toBe('BACKTEST')
  })

  it('isLive getter 反映目前模式', () => {
    const s = useAppModeStore()
    expect(s.isLive).toBe(false)
    s.setLive()
    expect(s.isLive).toBe(true)
  })
})
