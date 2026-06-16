/**
 * 真 bug 修復 — CandleChart scope prop 隔離。
 *
 * 驗:CandleChart scope='live' 只讀 live 命名空間的 fills → 只把 live 成交畫成
 * marker;往 backtest 命名空間灌的成交**不會**出現在這張 live 圖上(反之亦然)。
 *
 * mock ChartController 攔截 addMarker 命令式呼叫,只驗 CandleChart 對外可觀察行為。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'

const calls = {
  setHistory: vi.fn(),
  updateBar: vi.fn(),
  addMarker: vi.fn(),
  addPriceLine: vi.fn(),
  setEmaLine: vi.fn(),
  removeEmaLine: vi.fn(),
  reset: vi.fn(),
  fit: vi.fn(),
  destroy: vi.fn(),
}
vi.mock('@/lib/chartController', () => ({
  ChartController: vi.fn().mockImplementation(() => calls),
}))

import CandleChart from '@/components/chart/CandleChart.vue'
import { useFillsStore } from '@/stores/fills'
import type { OrderFilledData } from '@/types/contract'

function fill(orderId: string): OrderFilledData {
  return {
    type: 'OrderFilled',
    instrument_id: 'BTCUSDT-PERP.BINANCE',
    client_order_id: orderId,
    position_id: 'P-1',
    order_side: 'BUY',
    order_type: 'MARKET',
    last_qty: '0.100',
    last_px: '40000',
    ts_init: '1700000960000000000',
  } as unknown as OrderFilledData
}

beforeEach(() => {
  setActivePinia(createPinia())
  for (const fn of Object.values(calls)) fn.mockClear()
})

describe('CandleChart scope 隔離', () => {
  it("scope='live' 只把 live 命名空間成交畫成 marker,不畫 backtest 成交", async () => {
    // 先在兩個命名空間各放一筆成交。
    useFillsStore('backtest').add(fill('O-BT'))
    const w = mount(CandleChart, { props: { scope: 'live' } })
    await flushPromises()
    // 掛載時(immediate watcher)live 命名空間為空 → 不畫任何 marker。
    expect(calls.addMarker).not.toHaveBeenCalled()

    // 之後 live 命名空間新增一筆 → 畫一個 marker。
    useFillsStore('live').add(fill('O-LIVE'))
    await flushPromises()
    expect(calls.addMarker).toHaveBeenCalledTimes(1)

    // backtest 命名空間再新增 → live 圖不受影響(仍只 1 個 marker)。
    useFillsStore('backtest').add(fill('O-BT2'))
    await flushPromises()
    expect(calls.addMarker).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})
