/**
 * 真 bug 修復 — Live/Backtest 前端 state scope 命名空間隔離。
 *
 * 根因:store 全域單例 + dispatch 無條件寫全域 → BacktestView 串流(scope=backtest)
 * 寫進同一份 store,Live 面板/圖讀同一份 → 看到 backtest 的 marks/部位/PnL/成交。
 *
 * 修法:store 改 scope 工廠(`useXStore(scope)` → `defineStore('x:'+scope)`),
 * dispatch 帶 scope 路由到對應命名空間。本測試只驗「隔離語意」這個行為:
 * dispatch(msg, 'backtest') 不污染 live 命名空間,反之亦然。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { dispatchMessage } from '@/composables/dispatch'
import { useMarketStore } from '@/stores/market'
import { useFillsStore } from '@/stores/fills'
import { useOrdersStore } from '@/stores/orders'
import { usePositionsStore } from '@/stores/positions'
import { usePnlStore } from '@/stores/pnl'

beforeEach(() => setActivePinia(createPinia()))

function fillEnv(seq: number, orderId: string) {
  return {
    channel: 'fills' as const,
    seq,
    data: {
      type: 'OrderFilled',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: orderId,
      position_id: 'P-1',
      order_side: 'BUY',
      order_type: 'MARKET',
      last_qty: '0.100',
      last_px: '40000',
      ts_init: '1700000960000000000',
    },
  }
}

function barEnv(seq: number, time: number) {
  return {
    channel: 'bars' as const,
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

function orderEnv(seq: number, orderId: string) {
  return {
    channel: 'orders' as const,
    seq,
    data: {
      type: 'OrderInitialized',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      client_order_id: orderId,
      order_side: 'BUY',
      order_type: 'MARKET',
      quantity: '0.100',
      ts_init: '1700000960000000000',
    },
  }
}

function positionEnv(seq: number, posId: string, side = 'LONG') {
  return {
    channel: 'positions' as const,
    seq,
    data: {
      type: 'PositionOpened',
      instrument_id: 'BTCUSDT-PERP.BINANCE',
      position_id: posId,
      entry: 'BUY',
      side,
      signed_qty: 0.1,
      quantity: '0.100',
      last_px: '40000',
      avg_px_open: 40000,
      ts_init: '1700000960000000000',
    },
  }
}

function pnlEnv(seq: number, total: string) {
  return {
    channel: 'pnl' as const,
    seq,
    data: {
      type: 'AccountState',
      account_id: 'BINANCE-001',
      base_currency: 'USDT',
      balances: [{ total, locked: '0', free: total, currency: 'USDT' }],
      ts_init: '1700000000000000000',
    },
  }
}

describe('dispatch scope 隔離 — backtest 不污染 live', () => {
  it('fills:backtest dispatch → live 命名空間 fills 不含該成交', () => {
    dispatchMessage(fillEnv(1, 'O-BT'), 'backtest')
    expect(useFillsStore('backtest').fills).toHaveLength(1)
    expect(useFillsStore('live').fills).toHaveLength(0)
    expect(useFillsStore('live').fills.find((f) => f.client_order_id === 'O-BT')).toBeUndefined()
  })

  it('bars/orders/positions/pnl:backtest dispatch → live 命名空間全部不受影響', () => {
    dispatchMessage(barEnv(1, 1700000000), 'backtest')
    dispatchMessage(orderEnv(2, 'O-BT'), 'backtest')
    dispatchMessage(positionEnv(3, 'P-BT'), 'backtest')
    dispatchMessage(pnlEnv(4, '12345'), 'backtest')

    expect(useMarketStore('backtest').bars).toHaveLength(1)
    expect(useOrdersStore('backtest').orders).toHaveLength(1)
    expect(usePositionsStore('backtest').positions).toHaveLength(1)
    expect(usePnlStore('backtest').equity).toBe(12345)

    expect(useMarketStore('live').bars).toHaveLength(0)
    expect(useOrdersStore('live').orders).toHaveLength(0)
    expect(usePositionsStore('live').positions).toHaveLength(0)
    expect(usePnlStore('live').equity).toBeNull()
  })
})

describe('dispatch scope 隔離 — live 不污染 backtest', () => {
  it('fills:live dispatch → backtest 命名空間 fills 不含該成交', () => {
    dispatchMessage(fillEnv(1, 'O-LIVE'), 'live')
    expect(useFillsStore('live').fills).toHaveLength(1)
    expect(useFillsStore('backtest').fills).toHaveLength(0)
  })

  it('預設 scope = live(相容):dispatch 不帶 scope → 寫 live 命名空間', () => {
    dispatchMessage(fillEnv(1, 'O-DEFAULT'))
    expect(useFillsStore('live').fills).toHaveLength(1)
    expect(useFillsStore('backtest').fills).toHaveLength(0)
    // 預設工廠(不帶參數)= live 同一份。
    expect(useFillsStore().fills).toHaveLength(1)
  })
})

describe('scope 工廠同 id 共用、不同 id 分離', () => {
  it('同 scope 兩次呼叫拿到同一個 store 實例(Pinia id 快取)', () => {
    const a = useFillsStore('live')
    const b = useFillsStore('live')
    a.add(fillEnv(1, 'O-1').data as never)
    expect(b.fills).toHaveLength(1) // 同實例
  })
})
