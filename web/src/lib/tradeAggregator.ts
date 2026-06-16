/**
 * tradeAggregator — 把逐筆成交 TradeTick 聚合到「形成中、尚未收線」那根 K 線。
 *
 * 卡 B(Live 次秒 tick)核心視覺邏輯(純函式 deep module,無 Vue / LWC 依賴):
 * 每筆成交 {time(epoch 秒), price} 落入所屬分鐘 bucket(floor(time/bucket)*bucket),
 * 即時更新該根 candle 的 high/low/close(open 維持第一筆價),讓 Live 圖當前
 * K 線隨成交跳動,不必等 1m 收線。
 *
 * ⛔ 純視覺鐵律:此函式只算「形成中」那根的 OHLC;策略決策只看正式收線 1m bar
 * (走 bars channel)。trades 與 bars 刻意分兩條 channel —— bars 給策略 + 權威
 * 蠟燭,trades 只給視覺;1m 正式 bar 收線時由 market store 以它為準覆蓋同 time 那根。
 */
import type { BarDTO } from '@/types/contract'

const NS_PER_SEC = 1_000_000_000
/** 預設 bucket 秒數(1 分鐘 K 線)。5m 等可由呼叫端覆寫。 */
export const DEFAULT_BUCKET_SECONDS = 60

/** 單筆成交(視覺聚合輸入):time(epoch 秒)+ price(字串保留精度)。 */
export interface TradePoint {
  time: number
  price: string
}

/** 把 epoch 秒對齊到所屬 bucket 起始秒。 */
export function bucketStart(timeSec: number, bucketSeconds: number): number {
  return Math.floor(timeSec / bucketSeconds) * bucketSeconds
}

/**
 * 把一筆成交聚合進形成中 candle,回傳更新後的 candle。
 *
 * - ``forming === null``:開出一根新 candle(OHLC 皆 = 成交價,time = bucket)。
 * - 同 bucket:high=max、low=min、close=最新價;open 維持。
 * - 新(較大)bucket:換一根新 candle(OHLC 皆 = 成交價)。
 * - 較舊 bucket(亂序):回傳原 candle 不變(保護:不回退)。
 *
 * 不可變語意:回傳新物件(不就地改 forming),便於 store 比對/觸發響應式。
 */
export function aggregateTick(
  forming: BarDTO | null,
  trade: TradePoint,
  bucketSeconds: number = DEFAULT_BUCKET_SECONDS,
): BarDTO {
  const bucket = bucketStart(trade.time, bucketSeconds)

  // 無現有 candle,或進入新 bucket(新分鐘)→ 開一根新的形成中 candle。
  if (forming === null || bucket > forming.time) {
    return {
      ts: bucket * NS_PER_SEC,
      time: bucket,
      open: trade.price,
      high: trade.price,
      low: trade.price,
      close: trade.price,
      volume: '0',
    }
  }

  // 較舊 bucket(亂序)→ 不動(保護:形成中那根不回退)。
  if (bucket < forming.time) return forming

  // 同 bucket → 更新 high/low/close(open 維持)。
  const px = Number(trade.price)
  const high = px > Number(forming.high) ? trade.price : forming.high
  const low = px < Number(forming.low) ? trade.price : forming.low
  return { ...forming, high, low, close: trade.price }
}
