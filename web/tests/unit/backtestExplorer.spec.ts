/**
 * 卡 #21 (W2) — 行為測試:backtestExplorer store(run 列表 + 排序/比較 + 選取)
 * 與 useRunExplorer composable(選 run → 載成交 + 對應 bars → 重畫進出場)。
 *
 * 只驗 public state/getter/action 與 composable 對外行為(注入 fetch/api 決定論)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useBacktestExplorerStore } from '@/stores/backtestExplorer'
import type { RunSummary, TradeRecord } from '@/api/trades'

beforeEach(() => setActivePinia(createPinia()))

const RUN_A: RunSummary = {
  id: 1,
  strategy_name: 'ema_cross',
  instrument_id: 'BTCUSDT-PERP.BINANCE',
  timeframe: '1m',
  start_time: '2024-01-01T00:00:00Z',
  end_time: '2024-01-02T00:00:00Z',
  status: 'COMPLETED',
  total_return: '0.10',
  sharpe: '1.5',
  max_drawdown: '0.05',
  num_trades: 3,
  final_balance: '1100',
}
const RUN_B: RunSummary = {
  ...RUN_A,
  id: 2,
  total_return: '0.30',
  sharpe: '2.1',
  num_trades: 5,
}

describe('backtestExplorer store', () => {
  it('setRuns 載入 run 列表', () => {
    const s = useBacktestExplorerStore()
    s.setRuns([RUN_A, RUN_B])
    expect(s.runs).toHaveLength(2)
  })

  it('依指標排序(sharpe 降冪):較高 sharpe 在前', () => {
    const s = useBacktestExplorerStore()
    s.setRuns([RUN_A, RUN_B])
    s.sortBy('sharpe', 'desc')
    expect(s.sortedRuns[0].id).toBe(2) // RUN_B sharpe 2.1 > RUN_A 1.5
    expect(s.sortedRuns[1].id).toBe(1)
  })

  it('依指標排序(total_return 升冪):較低在前', () => {
    const s = useBacktestExplorerStore()
    s.setRuns([RUN_A, RUN_B])
    s.sortBy('total_return', 'asc')
    expect(s.sortedRuns[0].id).toBe(1) // 0.10 < 0.30
  })

  it('未設排序:sortedRuns 維持原序', () => {
    const s = useBacktestExplorerStore()
    s.setRuns([RUN_A, RUN_B])
    expect(s.sortedRuns.map((r) => r.id)).toEqual([1, 2])
  })

  it('select 設定 selectedRunId 與 selectedRun', () => {
    const s = useBacktestExplorerStore()
    s.setRuns([RUN_A, RUN_B])
    s.select(2)
    expect(s.selectedRunId).toBe(2)
    expect(s.selectedRun?.id).toBe(2)
  })

  it('setTrades 存目前選取 run 的成交', () => {
    const s = useBacktestExplorerStore()
    const trades: TradeRecord[] = [
      {
        id: 9,
        run_id: 2,
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        side: 'LONG',
        entry_price: '37000',
        exit_price: '37500',
        quantity: '0.5',
        sl: null,
        tp: null,
        pnl: '250',
        opened_at: '2024-01-01T00:00:00Z',
        closed_at: '2024-01-01T01:00:00Z',
      },
    ]
    s.setTrades(trades)
    expect(s.trades).toHaveLength(1)
  })
})

describe('useRunExplorer composable', () => {
  it('loadRuns:呼叫 api.fetchBacktestRuns 並填 store', async () => {
    const { useRunExplorer } = await import('@/composables/useRunExplorer')
    const fetchBacktestRuns = vi.fn().mockResolvedValue([RUN_A, RUN_B])
    const ex = useRunExplorer({
      api: { fetchBacktestRuns, fetchTrades: vi.fn(), fetchBars: vi.fn() },
    })
    await ex.loadRuns()
    expect(fetchBacktestRuns).toHaveBeenCalledOnce()
    expect(ex.store.runs).toHaveLength(2)
  })

  it('selectRun:載該 run 成交 + 用 run 的 symbol/timeframe/區間載 bars', async () => {
    const { useRunExplorer } = await import('@/composables/useRunExplorer')
    const trades: TradeRecord[] = [
      {
        id: 9,
        run_id: 1,
        instrument_id: 'BTCUSDT-PERP.BINANCE',
        side: 'LONG',
        entry_price: '37000',
        exit_price: '37500',
        quantity: '0.5',
        sl: '36600',
        tp: '37800',
        pnl: '250',
        opened_at: '2024-01-01T00:00:00Z',
        closed_at: '2024-01-01T01:00:00Z',
      },
    ]
    const bars = [{ ts: 1, time: 1704067200, open: '1', high: '1', low: '1', close: '1', volume: '1' }]
    const fetchTrades = vi.fn().mockResolvedValue(trades)
    const fetchBars = vi.fn().mockResolvedValue(bars)
    const ex = useRunExplorer({
      api: { fetchBacktestRuns: vi.fn().mockResolvedValue([RUN_A]), fetchTrades, fetchBars },
    })
    await ex.loadRuns()
    await ex.selectRun(1)

    expect(fetchTrades).toHaveBeenCalledWith(1)
    // bars 以 run 的 symbol + timeframe 載(start/end 以奈秒傳)。
    const barsArg = fetchBars.mock.calls[0][0]
    expect(barsArg.symbol).toBe('BTCUSDT-PERP.BINANCE')
    expect(barsArg.timeframe).toBe('1m')
    // 2024-01-01T00:00:00Z = 1704067200 秒 → 奈秒 1704067200e9
    expect(barsArg.start).toBe(1704067200 * 1e9)

    // 對外暴露重畫所需:bars + markers(每筆成交 2 個)+ priceLines(SL+TP)。
    expect(ex.bars.value).toHaveLength(1)
    expect(ex.markers.value).toHaveLength(2)
    expect(ex.priceLines.value).toHaveLength(2)
  })
})
