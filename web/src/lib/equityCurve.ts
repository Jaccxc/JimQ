/**
 * 卡 C — persisted trades → 累積權益曲線(純函式 deep module)。
 *
 * Backtest 主圖下方 PnL/權益副圖的資料源:把某 run 的 round-trip trades
 * (GET /backtests/{id}/trades)依出場時間排序後,逐筆累加已實現 PnL,輸出
 * 與 LWC LineSeries 對齊的點({ time, value })。time = 出場時間(closed_at)
 * epoch 秒(對齊主圖 K 線 UTCTimestamp);value = 至此累積權益。
 *
 * 不動 DB:前端用既有 explorer run trades 累加。pnl 為 null 視為 0 貢獻。
 */
import type { TradeRecord } from '@/api/trades'

/** 與 LWC LineSeries data point 對齊的最小規格。 */
export interface EquityPoint {
  time: number
  value: number
}

/** ISO-8601 datetime 字串 → epoch 秒(LWC UTCTimestamp)。 */
function isoToSec(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000)
}

/**
 * trades → 累積權益曲線。依 closed_at 升冪排序後逐筆累加 pnl(null→0)。
 *
 * @param trades 某 run 的 round-trip trades。
 * @param startingEquity 起始權益(預設 0,曲線即累積已實現 PnL)。
 */
export function tradesToEquityCurve(
  trades: TradeRecord[],
  startingEquity = 0,
): EquityPoint[] {
  const sorted = [...trades].sort(
    (a, b) => new Date(a.closed_at).getTime() - new Date(b.closed_at).getTime(),
  )
  // 逐筆累加;同一出場 time(同 minute 內多筆出場)合併成單一點,取該 time 的
  // 最終累積值。LWC LineSeries.setData 要求 time 嚴格遞增且唯一,否則拋
  // "data must be asc ordered by time"(實測 168 筆 round-trip 會踩到)。
  let equity = startingEquity
  const points: EquityPoint[] = []
  for (const t of sorted) {
    equity += t.pnl == null ? 0 : Number(t.pnl)
    const time = isoToSec(t.closed_at)
    const last = points[points.length - 1]
    if (last && last.time === time) last.value = equity
    else points.push({ time, value: equity })
  }
  return points
}
