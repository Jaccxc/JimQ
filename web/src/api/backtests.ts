/**
 * 卡 #20 (W1) — backtest 控制平面 REST client。
 *
 * - runBacktest:POST /api/v1/backtests/run({symbol,timeframe,strategy,params,
 *   start,end})→ {run_id, correlation_id, status}。後端建 PENDING 列 + 發命令
 *   到 Redis command stream;前端取 run_id 後訂 WS 即時看圖。
 * - fetchBacktestRun:GET /api/v1/backtests/{id} 輪詢 run 狀態(對齊 FastCRUD)。
 *
 * 走 vite proxy /api → http://127.0.0.1:8000。fetch 可注入(測試決定論)。
 */

/** launcher 表單請求 body(對齊 api BacktestRunRequest)。 */
export interface RunBacktestRequest {
  symbol: string
  timeframe: string
  strategy: string
  params: Record<string, unknown>
  /** ISO-8601 datetime(含時區)。 */
  start: string
  end: string
}

/** POST /backtests/run 回應(對齊 api BacktestRunAccepted)。 */
export interface RunBacktestAccepted {
  run_id: number
  correlation_id: string
  status: string
}

/** GET /backtests/{id} 回應(對齊 api BacktestRunRead;只取前端關心的欄位)。 */
export interface BacktestRunRead {
  id: number
  status: string
  num_trades?: number | null
  total_return?: string | number | null
  final_balance?: string | number | null
}

export interface ClientOptions {
  /** base path 覆寫(預設同源 /api/v1)。 */
  baseUrl?: string
  /** 注入 fetch(測試用)。 */
  fetchImpl?: typeof fetch
}

export async function runBacktest(
  req: RunBacktestRequest,
  opts: ClientOptions = {},
): Promise<RunBacktestAccepted> {
  const base = opts.baseUrl ?? '/api/v1'
  const f = opts.fetchImpl ?? fetch
  const res = await f(`${base}/backtests/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    throw new Error(`runBacktest ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as RunBacktestAccepted
}

export async function fetchBacktestRun(
  id: number,
  opts: ClientOptions = {},
): Promise<BacktestRunRead> {
  const base = opts.baseUrl ?? '/api/v1'
  const f = opts.fetchImpl ?? fetch
  const res = await f(`${base}/backtests/${id}`)
  if (!res.ok) {
    throw new Error(`fetchBacktestRun ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as BacktestRunRead
}
