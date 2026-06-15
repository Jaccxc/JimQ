/**
 * 行為測試:Pinia stores(market/orders/fills/positions/pnl/connection)。
 * 只驗 public state/getter/action 行為。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMarketStore } from '@/stores/market'
import { usePositionsStore } from '@/stores/positions'
import { useOrdersStore } from '@/stores/orders'
import { useFillsStore } from '@/stores/fills'
import { usePnlStore } from '@/stores/pnl'
import { useConnectionStore } from '@/stores/connection'
import type { BarDTO } from '@/types/contract'

beforeEach(() => setActivePinia(createPinia()))

const BAR: BarDTO = {
  ts: 1700000000000000000,
  time: 1700000000,
  open: '40000.0',
  high: '40005.0',
  low: '39995.0',
  close: '40000.0',
  volume: '10.0',
}

describe('market store', () => {
  it('setHistory 載入歷史 bars,lastBarTime 為最後一根 time', () => {
    const s = useMarketStore()
    const bars = [BAR, { ...BAR, ts: BAR.ts + 60e9, time: BAR.time + 60 }]
    s.setHistory(bars)
    expect(s.bars).toHaveLength(2)
    expect(s.lastBarTime).toBe(BAR.time + 60)
  })

  it('applyBar 同 time → 更新最後一根;新 time → 新增', () => {
    const s = useMarketStore()
    s.setHistory([BAR])
    s.applyBar({ ...BAR, close: '40010.0' }) // 同 time 更新
    expect(s.bars).toHaveLength(1)
    expect(s.bars[0].close).toBe('40010.0')
    s.applyBar({ ...BAR, ts: BAR.ts + 60e9, time: BAR.time + 60 }) // 新 bar
    expect(s.bars).toHaveLength(2)
    expect(s.lastBarTime).toBe(BAR.time + 60)
  })
})

describe('positions store', () => {
  it('upsert by position_id;FLAT 視為平倉移除', () => {
    const s = usePositionsStore()
    s.upsert({
      type: 'PositionOpened',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      position_id: 'P-1',
      entry: 'BUY',
      side: 'LONG',
      signed_qty: 0.1,
      quantity: '0.100',
      last_px: '39960.0',
      avg_px_open: 39960,
      ts_init: '1700000960000000000',
    })
    expect(s.positions).toHaveLength(1)
    expect(s.byId['P-1'].side).toBe('LONG')
    // 平倉。
    s.upsert({
      type: 'PositionClosed',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      position_id: 'P-1',
      entry: 'BUY',
      side: 'FLAT',
      signed_qty: 0,
      quantity: '0.000',
      last_px: '40500.0',
      avg_px_open: 39960,
      ts_init: '1700001020000000000',
    })
    expect(s.positions).toHaveLength(0)
  })
})

describe('orders + fills stores', () => {
  it('orders.add 累積委託', () => {
    const s = useOrdersStore()
    s.add({
      type: 'OrderInitialized',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: 'O-1',
      order_side: 'BUY',
      order_type: 'MARKET',
      quantity: '0.100',
      ts_init: '1700000960000000000',
    })
    expect(s.orders).toHaveLength(1)
  })

  it('fills.add 累積成交', () => {
    const s = useFillsStore()
    s.add({
      type: 'OrderFilled',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: 'O-1',
      position_id: 'P-1',
      order_side: 'BUY',
      order_type: 'MARKET',
      last_qty: '0.100',
      last_px: '39960.0',
      ts_init: '1700000960000000000',
    })
    expect(s.fills).toHaveLength(1)
  })
})

describe('pnl store', () => {
  it('last-value-wins:set 覆寫最新帳戶餘額', () => {
    const s = usePnlStore()
    s.set({
      type: 'AccountState',
      account_id: 'BINANCE-001',
      base_currency: 'USDT',
      balances: [{ total: '1000000', locked: '0', free: '1000000', currency: 'USDT' }],
      ts_init: '1700000000000000000',
    })
    expect(s.equity).toBe(1000000)
    s.set({
      type: 'AccountState',
      account_id: 'BINANCE-001',
      base_currency: 'USDT',
      balances: [{ total: '999000', locked: '0', free: '999000', currency: 'USDT' }],
      ts_init: '1700001000000000000',
    })
    expect(s.equity).toBe(999000)
  })
})

describe('connection store', () => {
  it('追蹤 status 與 lastSeq(取最大,單調不回退)', () => {
    const s = useConnectionStore()
    expect(s.status).toBe('disconnected')
    s.setStatus('connected')
    expect(s.status).toBe('connected')
    s.observeSeq(5)
    s.observeSeq(3) // 較小不回退
    s.observeSeq(9)
    expect(s.lastSeq).toBe(9)
  })

  it('重連次數 incReconnect / resetReconnect', () => {
    const s = useConnectionStore()
    s.incReconnect()
    s.incReconnect()
    expect(s.reconnectAttempts).toBe(2)
    s.resetReconnect()
    expect(s.reconnectAttempts).toBe(0)
  })
})
