/**
 * 卡 C — 行為測試:useRunExplorer 暴露 equity 權益曲線(供主圖下方副圖)。
 *
 * 選 run → 載成交後,equity 為該 run trades 的累積權益曲線;換 run 重算
 * (舊 run 曲線不殘留)。只驗 composable 對外行為(注入 fake api 決定論)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
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
  num_trades: 2,
  final_balance: '1100',
}
const RUN_B: RunSummary = { ...RUN_A, id: 2, instrument_id: 'ETHUSDT-PERP.BINANCE' }

function mkTrade(id: number, pnl: string, closedAt: string): TradeRecord {
  return {
    id,
    run_id: 1,
    instrument_id: 'BTCUSDT-PERP.BINANCE',
    side: 'LONG',
    entry_price: '100',
    exit_price: '110',
    quantity: '1',
    sl: null,
    tp: null,
    pnl,
    opened_at: closedAt,
    closed_at: closedAt,
  }
}

const bars = [{ ts: 1, time: 1704067200, open: '1', high: '1', low: '1', close: '1', volume: '1' }]

describe('useRunExplorer equity', () => {
  it('選 run 後 equity 為該 run trades 的累積權益曲線', async () => {
    const { useRunExplorer } = await import('@/composables/useRunExplorer')
    const tradesA = [
      mkTrade(1, '100', '2024-01-01T00:00:00Z'),
      mkTrade(2, '-40', '2024-01-01T01:00:00Z'),
    ]
    const ex = useRunExplorer({
      api: {
        fetchBacktestRuns: vi.fn().mockResolvedValue([RUN_A]),
        fetchTrades: vi.fn().mockResolvedValue(tradesA),
        fetchBars: vi.fn().mockResolvedValue(bars),
      },
    })
    await ex.loadRuns()
    await ex.selectRun(1)
    expect(ex.equity.value.map((p) => p.value)).toEqual([100, 60])
  })

  it('換 run → equity 重算,不殘留舊 run 曲線', async () => {
    const { useRunExplorer } = await import('@/composables/useRunExplorer')
    const fetchTrades = vi
      .fn()
      .mockResolvedValueOnce([mkTrade(1, '100', '2024-01-01T00:00:00Z')])
      .mockResolvedValueOnce([mkTrade(9, '5', '2024-01-01T03:00:00Z')])
    const ex = useRunExplorer({
      api: {
        fetchBacktestRuns: vi.fn().mockResolvedValue([RUN_A, RUN_B]),
        fetchTrades,
        fetchBars: vi.fn().mockResolvedValue(bars),
      },
    })
    await ex.loadRuns()
    await ex.selectRun(1)
    expect(ex.equity.value.map((p) => p.value)).toEqual([100])
    await ex.selectRun(2)
    // 新 run 只有一筆 +5 → 曲線重算成 [5],舊 [100] 不殘留。
    expect(ex.equity.value.map((p) => p.value)).toEqual([5])
  })
})
