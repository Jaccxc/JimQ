/**
 * order/fill 事件 → Lightweight Charts marker / priceLine 規格(純函式 deep module)。
 *
 * 抽成可測純函式:輸入後端事件 data,輸出與 LWC API 對齊的「規格物件」,
 * 由元件層命令式套用(createSeriesMarkers / series.createPriceLine)。
 *
 * 對齊 LWC v5:
 * - SeriesMarker(time/position/shape/color/text);v5 用 createSeriesMarkers(series, markers)。
 * - PriceLineOptions(price/color/lineStyle/title);series.createPriceLine(opts)。
 *
 * 真相來源:api/tests/test_nautilus_consumer.py 的實測 payload。
 * - fill(OrderFilled):order_side BUY/SELL、last_px、last_qty、ts_init(奈秒)。
 * - order(OrderInitialized):bracket 子單 STOP_MARKET 帶 trigger_price(SL)、
 *   LIMIT 帶 price(TP);MARKET 進場單無價。
 */
import type { OrderFilledData, OrderInitializedData } from '@/types/contract'

const NS_PER_SEC = 1_000_000_000

/** marker 顏色(進/出場)。 */
const BUY_COLOR = '#26a69a'
const SELL_COLOR = '#ef5350'

/** 出場 marker 顏色(amber):與進場的多/空綠紅明確區隔,避免「同一筆畫兩次」錯覺。 */
const EXIT_COLOR = '#f0b90b'

/** priceLine 顏色。 */
const SL_COLOR = '#ef5350'
const TP_COLOR = '#26a69a'

/** ns 字串/數字 → epoch 秒(LWC UTCTimestamp)。 */
function nsToSec(ts: string | number): number {
  return Math.floor(Number(ts) / NS_PER_SEC)
}

/** 與 LWC SeriesMarker 對齊的最小規格(v5 shape 支援 arrowUp/arrowDown/circle/square)。 */
export interface MarkerSpec {
  time: number
  position: 'aboveBar' | 'belowBar'
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square'
  color: string
  text: string
}

/** 與 LWC PriceLineOptions 對齊的規格 + 前端追蹤用 id/kind。 */
export interface PriceLineSpec {
  id: string
  kind: 'SL' | 'TP'
  price: number
  color: string
  title: string
}

/** 成交(fill)→ 進出場箭頭 marker。 */
export function fillToMarker(fill: OrderFilledData): MarkerSpec {
  const isBuy = fill.order_side === 'BUY'
  const px = Number(fill.last_px)
  return {
    time: nsToSec(fill.ts_init),
    position: isBuy ? 'belowBar' : 'aboveBar',
    shape: isBuy ? 'arrowUp' : 'arrowDown',
    color: isBuy ? BUY_COLOR : SELL_COLOR,
    text: `${fill.order_side} ${fill.last_qty} @ ${px}`,
  }
}

/**
 * 委託初始化(order)→ SL/TP 水平線。
 * bracket 的 SL 子單為 STOP_MARKET(trigger_price);TP 子單為 LIMIT(price)。
 * MARKET 進場單無價,回空陣列。
 */
export function orderToPriceLines(order: OrderInitializedData): PriceLineSpec[] {
  const lines: PriceLineSpec[] = []
  const type = order.order_type
  if (type === 'STOP_MARKET' || type === 'STOP' || type === 'STOP_LIMIT') {
    if (order.trigger_price != null) {
      lines.push({
        id: `${order.client_order_id}:SL`,
        kind: 'SL',
        price: Number(order.trigger_price),
        color: SL_COLOR,
        title: `SL ${order.trigger_price}`,
      })
    }
  } else if (type === 'LIMIT') {
    if (order.price != null) {
      lines.push({
        id: `${order.client_order_id}:TP`,
        kind: 'TP',
        price: Number(order.price),
        color: TP_COLOR,
        title: `TP ${order.price}`,
      })
    }
  }
  return lines
}

// --- 卡 #21 (W2):persisted trade(GET /backtests/{id}/trades 的列)映射 --------
//
// 重載歷史 backtest 的進出場時,trade 已是 round-trip(進場 + 出場)的彙整列,
// 非逐筆 fill/order 事件。故 trade → 兩個 marker(進場於 opened_at、出場於
// closed_at)+ SL/TP priceLine(若有 bracket)。time 由 ISO-8601 → epoch 秒。

/** ISO-8601 datetime 字串 → epoch 秒(LWC UTCTimestamp)。 */
function isoToSec(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000)
}

/**
 * persisted trade → 進場 + 出場 marker(視覺可區分,卡 D)。
 *
 * 進場:**實心箭頭**指向部位方向(LONG=arrowUp/belowBar、SHORT=arrowDown/aboveBar),
 *       色用多/空綠紅,文字 `Entry <side> <qty> @ <entry_price>`。
 * 出場:**非箭頭形狀(circle)**+ 獨立 amber 色,文字 `Exit @ <exit_price> (PnL ...)`。
 * 進場與出場的 shape 與 color 皆不同,避免 round-trip 看似「同一筆畫了兩次」。
 */
export function tradeToMarkers(trade: import('@/api/trades').TradeRecord): MarkerSpec[] {
  const isLong = trade.side === 'LONG'
  const entry: MarkerSpec = {
    time: isoToSec(trade.opened_at),
    position: isLong ? 'belowBar' : 'aboveBar',
    shape: isLong ? 'arrowUp' : 'arrowDown',
    color: isLong ? BUY_COLOR : SELL_COLOR,
    text: `Entry ${trade.side} ${trade.quantity} @ ${trade.entry_price}`,
  }
  const exit: MarkerSpec = {
    time: isoToSec(trade.closed_at),
    // 出場放在部位反向的另一側,且用 circle + amber 與進場箭頭明確分離。
    position: isLong ? 'aboveBar' : 'belowBar',
    shape: 'circle',
    color: EXIT_COLOR,
    text: `Exit @ ${trade.exit_price}${trade.pnl != null ? ` (PnL ${trade.pnl})` : ''}`,
  }
  return [entry, exit]
}

/** persisted trade → SL/TP priceLine(欄位為 null 時不產生對應線)。 */
export function tradeToPriceLines(
  trade: import('@/api/trades').TradeRecord,
): PriceLineSpec[] {
  const lines: PriceLineSpec[] = []
  if (trade.sl != null) {
    lines.push({
      id: `trade-${trade.id}:SL`,
      kind: 'SL',
      price: Number(trade.sl),
      color: SL_COLOR,
      title: `SL ${trade.sl}`,
    })
  }
  if (trade.tp != null) {
    lines.push({
      id: `trade-${trade.id}:TP`,
      kind: 'TP',
      price: Number(trade.tp),
      color: TP_COLOR,
      title: `TP ${trade.tp}`,
    })
  }
  return lines
}
