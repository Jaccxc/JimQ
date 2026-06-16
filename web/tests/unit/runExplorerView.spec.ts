/**
 * 卡 C — 行為測試:RunExplorerView 選不同 run → 主圖整體重畫成該 run
 * (setHistory 新 bars + setMarkers 全量替換,舊 marker 不殘留)+ 權益副圖
 * 隨 run 重算(setEquityLine 新曲線)。
 *
 * mock @/lib/chartController 攔截命令式呼叫;注入 fake explorer api 達決定論。
 * 只驗對 controller 的行為(換 run 的視覺重畫),不驗 LWC 內部。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'

const calls = {
  setHistory: vi.fn(),
  setMarkers: vi.fn(),
  clearPriceLines: vi.fn(),
  addPriceLine: vi.fn(),
  setEquityLine: vi.fn(),
  clearEquityLine: vi.fn(),
  destroy: vi.fn(),
}
vi.mock('@/lib/chartController', () => ({
  ChartController: vi.fn().mockImplementation(() => calls),
}))

import RunExplorerView from '@/views/RunExplorerView.vue'
import type { RunSummary, TradeRecord } from '@/api/trades'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000
function bar(time: number): BarDTO {
  return { ts: time * NS, time, open: '1', high: '2', low: '0', close: '1', volume: '1' }
}

const RUN_A: RunSummary = {
  id: 1,
  strategy_name: 'ema_cross',
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  timeframe: '1m',
  start_time: '2024-01-01T00:00:00Z',
  end_time: '2024-01-02T00:00:00Z',
  status: 'COMPLETED',
  total_return: '0.1',
  sharpe: '1',
  max_drawdown: '0.05',
  num_trades: 1,
  final_balance: '1100',
}
const RUN_B: RunSummary = { ...RUN_A, id: 2, instrument_id: 'ETHUSDT-PERP.BINANCE' }

function trade(id: number, pnl: string, closedAt: string): TradeRecord {
  return {
    id,
    run_id: id,
    instrument_id: 'X',
    side: 'LONG',
    entry_price: '100',
    exit_price: '110',
    quantity: '1',
    sl: null,
    tp: null,
    pnl,
    opened_at: '2024-01-01T00:00:00Z',
    closed_at: closedAt,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  for (const fn of Object.values(calls)) fn.mockClear()
})

function mountView() {
  const fetchTrades = vi
    .fn()
    .mockResolvedValueOnce([trade(1, '100', '2024-01-01T00:00:00Z')]) // run A:1 筆 → 2 marker
    .mockResolvedValueOnce([
      trade(2, '10', '2024-01-01T01:00:00Z'),
      trade(3, '20', '2024-01-01T02:00:00Z'),
    ]) // run B:2 筆 → 4 marker
  const fetchBars = vi
    .fn()
    .mockResolvedValueOnce([bar(1704067200)]) // run A bars
    .mockResolvedValueOnce([bar(1704070800), bar(1704074400)]) // run B bars
  const w = mount(RunExplorerView, {
    props: {
      api: {
        fetchBacktestRuns: vi.fn().mockResolvedValue([RUN_A, RUN_B]),
        fetchTrades,
        fetchBars,
      },
    },
  })
  return w
}

describe('RunExplorerView 換 run 重畫主圖 + 權益副圖', () => {
  it('選 run A → 主圖畫 A 的 bars + marker;選 run B → 全量換成 B(舊 marker 不殘留)', async () => {
    const w = mountView()
    await flushPromises()

    await w.get('[data-testid="run-row-1"]').trigger('click')
    await flushPromises()
    // run A:1 筆 trade → setMarkers 收到 2 個 marker。
    const aMarkers = calls.setMarkers.mock.calls.at(-1)![0]
    expect(aMarkers).toHaveLength(2)
    const aBars = calls.setHistory.mock.calls.at(-1)![0]
    expect(aBars).toHaveLength(1)

    await w.get('[data-testid="run-row-2"]').trigger('click')
    await flushPromises()
    // run B:2 筆 trade → setMarkers 全量替換成 4 個(非 append 累積)。
    const bMarkers = calls.setMarkers.mock.calls.at(-1)![0]
    expect(bMarkers).toHaveLength(4)
    // 主圖 bars 換成 B 的 2 根。
    const bBars = calls.setHistory.mock.calls.at(-1)![0]
    expect(bBars).toHaveLength(2)
    expect(bBars[0].time).toBe(1704070800)
  })

  it('選不同 run → 權益副圖隨 run 重算(setEquityLine 新曲線)', async () => {
    const w = mountView()
    await flushPromises()

    await w.get('[data-testid="run-row-1"]').trigger('click')
    await flushPromises()
    // run A:單筆 +100 → 曲線 [100]。
    expect(calls.setEquityLine.mock.calls.at(-1)![0].map((p: { value: number }) => p.value)).toEqual([100])

    await w.get('[data-testid="run-row-2"]').trigger('click')
    await flushPromises()
    // run B:+10、+20 累加 → [10, 30](重算,非沿用 A)。
    expect(calls.setEquityLine.mock.calls.at(-1)![0].map((p: { value: number }) => p.value)).toEqual([10, 30])
  })
})
