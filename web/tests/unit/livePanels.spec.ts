/**
 * 卡 #28 (P2-S2) — Live 頁面板接**真 live** 值(行為,透過 public interface)。
 *
 * 驗收:testnet paper 單事件經 WS 信封(dispatchMessage 路由到 stores)後,
 * Live 頁的 PnlWidget / PositionsTable / OrdersTable(成交)面板渲染出該 live 值,
 * 取代先前 read-only 佔位。只驗「面板顯示 store 的 live 值」這個行為,
 * 不打真網路(注入信封模擬 testnet 事件流)。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { dispatchMessage } from '@/composables/dispatch'
import PnlWidget from '@/components/panels/PnlWidget.vue'
import PositionsTable from '@/components/panels/PositionsTable.vue'
import OrdersTable from '@/components/panels/OrdersTable.vue'

beforeEach(() => setActivePinia(createPinia()))

describe('Live 頁面板接真 live 值(P2-S2 paper 單事件)', () => {
  it('PnlWidget 顯示 testnet AccountState 權益(取代佔位 —)', async () => {
    const w = mount(PnlWidget)
    // 接事件前:佔位 —。
    expect(w.get('[data-testid="pnl-widget"]').text()).toContain('—')
    dispatchMessage({
      channel: 'pnl',
      seq: 1,
      data: {
        type: 'AccountState',
        account_id: 'BINANCE-TESTNET-001',
        base_currency: 'USDT',
        balances: [{ total: '5000', locked: '0', free: '5000', currency: 'USDT' }],
        ts_init: '1700000000000000000',
      },
    })
    // 接 testnet 帳戶事件後:顯示真權益。
    await flushPromises()
    const txt = w.get('[data-testid="pnl-widget"]').text()
    expect(txt).toContain('5,000')
    expect(txt).toContain('USDT')
  })

  it('PositionsTable 顯示 paper 單開倉部位(取代「無持倉」)', async () => {
    const w = mount(PositionsTable)
    expect(w.get('[data-testid="positions-table"]').text()).toContain('無持倉')
    dispatchMessage({
      channel: 'positions',
      seq: 2,
      data: {
        type: 'PositionOpened',
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        position_id: 'BTCUSDT-PERP.BINANCE-LIVE',
        entry: 'BUY',
        side: 'LONG',
        signed_qty: 0.001,
        quantity: '0.001',
        last_px: '66000',
        avg_px_open: 66000,
        ts_init: '1700000960000000000',
      },
    })
    await flushPromises()
    const txt = w.get('[data-testid="positions-table"]').text()
    expect(txt).toContain('LONG')
    expect(txt).toContain('0.001')
    expect(txt).not.toContain('無持倉')
  })

  it('OrdersTable 顯示 paper 單成交(取代「無成交」)', async () => {
    const w = mount(OrdersTable)
    expect(w.get('[data-testid="fills-table"]').text()).toContain('無成交')
    dispatchMessage({
      channel: 'fills',
      seq: 3,
      data: {
        type: 'OrderFilled',
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        client_order_id: 'O-LIVE-1',
        position_id: 'BTCUSDT-PERP.BINANCE-LIVE',
        order_side: 'BUY',
        order_type: 'MARKET',
        last_qty: '0.001',
        last_px: '66000',
        ts_init: '1700000960000000000',
      },
    })
    await flushPromises()
    const txt = w.get('[data-testid="fills-table"]').text()
    expect(txt).toContain('BUY')
    expect(txt).toContain('0.001')
    expect(txt).not.toContain('無成交')
  })

  it('FLAT 部位(平倉)從面板移除 → round-trip 收尾', async () => {
    const w = mount(PositionsTable)
    const open = {
      channel: 'positions' as const,
      seq: 4,
      data: {
        type: 'PositionOpened',
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        position_id: 'P-RT',
        entry: 'BUY',
        side: 'LONG',
        signed_qty: 0.001,
        quantity: '0.001',
        last_px: '66000',
        avg_px_open: 66000,
        ts_init: '1700000960000000000',
      },
    }
    dispatchMessage(open)
    dispatchMessage({
      ...open,
      seq: 5,
      data: { ...open.data, type: 'PositionClosed', side: 'FLAT', signed_qty: 0 },
    })
    await flushPromises()
    expect(w.get('[data-testid="positions-table"]').text()).toContain('無持倉')
  })
})
