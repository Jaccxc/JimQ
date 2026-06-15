/**
 * 行為測試:WS 信封分派(dispatchMessage)→ Pinia stores + connection。
 *
 * 涵蓋:channel 路由、snapshot/live/heartbeat 控制訊息、seq 觀察(last_seq)。
 * 真相來源:api/src/app/ws/stream.py 信封流、test_nautilus_consumer.py payload。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { dispatchMessage } from '@/composables/dispatch'
import { useMarketStore } from '@/stores/market'
import { usePositionsStore } from '@/stores/positions'
import { useOrdersStore } from '@/stores/orders'
import { useFillsStore } from '@/stores/fills'
import { usePnlStore } from '@/stores/pnl'
import { useConnectionStore } from '@/stores/connection'
import type { StreamEnvelope } from '@/types/contract'

beforeEach(() => setActivePinia(createPinia()))

function barEnv(seq: number, time: number): StreamEnvelope {
  return {
    channel: 'bars',
    seq,
    data: {
      type: 'Bar',
      ts: time * 1e9,
      time,
      open: '40000',
      high: '40010',
      low: '39990',
      close: '40005',
      volume: '1.0',
    },
  }
}

describe('dispatchMessage channel 路由', () => {
  it('bars 信封 → market.applyBar', () => {
    dispatchMessage(barEnv(1, 1700000000))
    expect(useMarketStore().bars).toHaveLength(1)
  })

  it('positions 信封 → positions.upsert', () => {
    dispatchMessage({
      channel: 'positions',
      seq: 2,
      data: {
        type: 'PositionOpened',
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        position_id: 'P-1',
        entry: 'BUY',
        side: 'LONG',
        signed_qty: 0.1,
        quantity: '0.100',
        last_px: '39960',
        avg_px_open: 39960,
        ts_init: '1700000960000000000',
      },
    })
    expect(usePositionsStore().positions).toHaveLength(1)
  })

  it('orders 信封 → orders.add', () => {
    dispatchMessage({
      channel: 'orders',
      seq: 3,
      data: {
        type: 'OrderInitialized',
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        client_order_id: 'O-1',
        order_side: 'BUY',
        order_type: 'MARKET',
        quantity: '0.100',
        ts_init: '1700000960000000000',
      },
    })
    expect(useOrdersStore().orders).toHaveLength(1)
  })

  it('fills 信封 → fills.add', () => {
    dispatchMessage({
      channel: 'fills',
      seq: 4,
      data: {
        type: 'OrderFilled',
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        client_order_id: 'O-1',
        position_id: 'P-1',
        order_side: 'BUY',
        order_type: 'MARKET',
        last_qty: '0.100',
        last_px: '39960',
        ts_init: '1700000960000000000',
      },
    })
    expect(useFillsStore().fills).toHaveLength(1)
  })

  it('pnl 信封 → pnl.set', () => {
    dispatchMessage({
      channel: 'pnl',
      seq: 5,
      data: {
        type: 'AccountState',
        account_id: 'BINANCE-001',
        base_currency: 'USDT',
        balances: [{ total: '1000000', locked: '0', free: '1000000', currency: 'USDT' }],
        ts_init: '1700000000000000000',
      },
    })
    expect(usePnlStore().equity).toBe(1000000)
  })
})

describe('dispatchMessage seq / 控制訊息', () => {
  it('每個信封都更新 connection.lastSeq(單調)', () => {
    const conn = useConnectionStore()
    dispatchMessage(barEnv(7, 1700000000))
    dispatchMessage(barEnv(5, 1700000060)) // 較小 seq(補洞亂序)不回退
    dispatchMessage(barEnv(12, 1700000120))
    expect(conn.lastSeq).toBe(12)
  })

  it('{type:"live"} → connection.status = live', () => {
    const conn = useConnectionStore()
    conn.setStatus('connected')
    dispatchMessage({ type: 'live' })
    expect(conn.status).toBe('live')
  })

  it('{type:"heartbeat"} → 記錄 heartbeat,不動 stores', () => {
    const conn = useConnectionStore()
    dispatchMessage({ type: 'heartbeat', ts: 1700000000.5 })
    expect(conn.lastHeartbeat).toBe(1700000000.5)
    expect(useMarketStore().bars).toHaveLength(0)
  })

  it('snapshot 信封照常分派並更新 lastSeq', () => {
    const conn = useConnectionStore()
    dispatchMessage({ ...barEnv(3, 1700000000), snapshot: true })
    expect(useMarketStore().bars).toHaveLength(1)
    expect(conn.lastSeq).toBe(3)
  })
})
