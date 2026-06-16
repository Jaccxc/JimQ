/**
 * 卡 #21 (W2) — backtest 結果瀏覽器 store。
 *
 * 持有歷史 run 列表(含指標)、目前排序、選取的 run 與其成交。run 列表視圖據此
 * 依指標排序/比較;選取某 run 後 composable 載成交 + 對應 bars 重畫。
 */
import { defineStore } from 'pinia'
import type { RunSummary, TradeRecord } from '@/api/trades'

/** 可排序的數值指標欄位。 */
export type SortKey =
  | 'total_return'
  | 'sharpe'
  | 'max_drawdown'
  | 'num_trades'
  | 'final_balance'
  | 'id'
export type SortDir = 'asc' | 'desc'

interface State {
  runs: RunSummary[]
  sortKey: SortKey | null
  sortDir: SortDir
  selectedRunId: number | null
  trades: TradeRecord[]
}

/** 指標值 → number(null/字串安全);null 排在最後。 */
function metricValue(run: RunSummary, key: SortKey): number {
  const v = run[key] as string | number | null
  if (v == null) return Number.NEGATIVE_INFINITY
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isNaN(n) ? Number.NEGATIVE_INFINITY : n
}

export const useBacktestExplorerStore = defineStore('backtestExplorer', {
  state: (): State => ({
    runs: [],
    sortKey: null,
    sortDir: 'desc',
    selectedRunId: null,
    trades: [],
  }),
  getters: {
    /** 依目前排序鍵/方向的 run 列表(未設排序則維持原序)。 */
    sortedRuns(s): RunSummary[] {
      if (s.sortKey == null) return s.runs
      const key = s.sortKey
      const dir = s.sortDir === 'asc' ? 1 : -1
      // 複製後排序(不就地改原陣列,保留載入順序)。
      return [...s.runs].sort((a, b) => (metricValue(a, key) - metricValue(b, key)) * dir)
    },
    selectedRun(s): RunSummary | null {
      return s.runs.find((r) => r.id === s.selectedRunId) ?? null
    },
  },
  actions: {
    setRuns(runs: RunSummary[]) {
      this.runs = runs
    },
    sortBy(key: SortKey, dir: SortDir = 'desc') {
      this.sortKey = key
      this.sortDir = dir
    },
    select(runId: number) {
      this.selectedRunId = runId
      this.trades = [] // 換 run 先清舊成交,避免殘留。
    },
    setTrades(trades: TradeRecord[]) {
      this.trades = trades
    },
  },
})
