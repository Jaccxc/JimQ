/**
 * 卡 #21 (W2) — backtest run 列表 + 該 run 成交 REST client。
 *
 * - fetchBacktestRuns:GET /api/v1/backtests(FastCRUD 分頁 {data,total_count,...})
 *   → 取 data 陣列(run 列表 + 指標),供結果瀏覽器排序/比較。
 * - fetchTrades:GET /api/v1/backtests/{id}/trades → 該 run 的成交(進出場/SL/TP/
 *   PnL),依 opened_at 排序;前端重載 K 線後用 tradeMapping 畫進出場 marker/SL/TP。
 *
 * 走 vite proxy /api → http://127.0.0.1:8000。fetch 可注入(測試決定論)。
 */

/** GET /backtests/{id}/trades 的一列(對齊 api BacktestTradeRead)。 */
export interface TradeRecord {
  id: number
  run_id: number
  instrument_id: string
  side: 'LONG' | 'SHORT'
  entry_price: string
  exit_price: string
  quantity: string
  sl: string | null
  tp: string | null
  pnl: string | null
  /** ISO-8601 datetime(含時區)。 */
  opened_at: string
  closed_at: string
}

/** GET /backtests 的一列(對齊 api BacktestRunRead;只取瀏覽器關心的欄位)。 */
export interface RunSummary {
  id: number
  strategy_name: string
  instrument_id: string
  timeframe: string
  start_time: string
  end_time: string
  status: string
  total_return: string | number | null
  sharpe: string | number | null
  max_drawdown: string | number | null
  num_trades: number | null
  final_balance: string | number | null
}

export interface ClientOptions {
  /** base path 覆寫(預設同源 /api/v1)。 */
  baseUrl?: string
  /** 注入 fetch(測試用)。 */
  fetchImpl?: typeof fetch
}

/** FastCRUD 分頁回應 envelope(只取 data)。 */
interface Paginated<T> {
  data: T[]
  total_count?: number
}

export async function fetchBacktestRuns(opts: ClientOptions = {}): Promise<RunSummary[]> {
  const base = opts.baseUrl ?? '/api/v1'
  const f = opts.fetchImpl ?? fetch
  const res = await f(`${base}/backtests?page=1&itemsPerPage=100`)
  if (!res.ok) {
    throw new Error(`fetchBacktestRuns ${res.status} ${res.statusText ?? ''}`.trim())
  }
  const body = (await res.json()) as Paginated<RunSummary>
  return body.data ?? []
}

export async function fetchTrades(
  runId: number,
  opts: ClientOptions = {},
): Promise<TradeRecord[]> {
  const base = opts.baseUrl ?? '/api/v1'
  const f = opts.fetchImpl ?? fetch
  const res = await f(`${base}/backtests/${runId}/trades`)
  if (!res.ok) {
    throw new Error(`fetchTrades ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as TradeRecord[]
}
