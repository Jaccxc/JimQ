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
