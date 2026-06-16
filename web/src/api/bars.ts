/**
 * 歷史 bars REST client(對齊 #8 GET /api/v1/bars)。
 *
 * query:symbol / timeframe / start(epoch 奈秒,含)/ end(epoch 奈秒,含)。
 * 回 BarDTO[]。走 vite proxy /api → http://127.0.0.1:8000。
 */
import type { BarDTO } from '@/types/contract'

export interface FetchBarsParams {
  symbol: string
  timeframe: string
  start?: number
  end?: number
  /** base path 覆寫(預設同源 /api/v1)。 */
  baseUrl?: string
}

export async function fetchBars(params: FetchBarsParams): Promise<BarDTO[]> {
  const base = params.baseUrl ?? '/api/v1'
  const q = new URLSearchParams()
  q.set('symbol', params.symbol)
  q.set('timeframe', params.timeframe)
  if (params.start != null) q.set('start', String(params.start))
  if (params.end != null) q.set('end', String(params.end))
  const res = await fetch(`${base}/bars?${q.toString()}`)
  if (!res.ok) {
    throw new Error(`fetchBars ${res.status} ${res.statusText}`)
  }
  return (await res.json()) as BarDTO[]
}

/**
 * Catalog 資料區間 client(對齊 GET /api/v1/bars/range)。
 *
 * 回某 symbol+timeframe 在 catalog 的實際 {start,end,count}(bar ts_init 奈秒;
 * 空則 start/end=null、count=0)。launcher 掛載時用來動態填**有資料的**預設日期。
 * fetch 可注入(測試決定論)。
 */
export interface FetchBarRangeParams {
  symbol: string
  timeframe: string
  /** base path 覆寫(預設同源 /api/v1)。 */
  baseUrl?: string
}

export interface BarRange {
  start: number | null
  end: number | null
  count: number
}

export async function fetchBarRange(
  params: FetchBarRangeParams,
  fetchImpl: typeof fetch = fetch,
): Promise<BarRange> {
  const base = params.baseUrl ?? '/api/v1'
  const q = new URLSearchParams()
  q.set('symbol', params.symbol)
  q.set('timeframe', params.timeframe)
  const res = await fetchImpl(`${base}/bars/range?${q.toString()}`)
  if (!res.ok) {
    throw new Error(`fetchBarRange ${res.status} ${res.statusText}`)
  }
  return (await res.json()) as BarRange
}

/**
 * Live 頁近期真 klines client(對齊 #30 GET /api/v1/live/bars)。
 *
 * 後端從 Binance testnet 期貨公開 klines 取最近 ``limit`` 根 → BarDTO[](與 live
 * WS bar 同 venue,價位一致 ~66k)。Live 頁初始載入用此端點取代 2024 catalog,
 * 消除 40k/66k 斷裂。fetch 可注入(測試決定論)。
 */
export interface FetchLiveBarsParams {
  symbol: string
  /** Binance kline interval,如 1m / 5m(預設 1m)。 */
  timeframe?: string
  /** 取最近 N 根(預設 500,後端上限 1500)。 */
  limit?: number
  /** base path 覆寫(預設同源 /api/v1)。 */
  baseUrl?: string
}

export async function fetchLiveBars(
  params: FetchLiveBarsParams,
  fetchImpl: typeof fetch = fetch,
): Promise<BarDTO[]> {
  const base = params.baseUrl ?? '/api/v1'
  const q = new URLSearchParams()
  q.set('symbol', params.symbol)
  q.set('timeframe', params.timeframe ?? '1m')
  q.set('limit', String(params.limit ?? 500))
  const res = await fetchImpl(`${base}/live/bars?${q.toString()}`)
  if (!res.ok) {
    throw new Error(`fetchLiveBars ${res.status} ${res.statusText}`)
  }
  return (await res.json()) as BarDTO[]
}
