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

/** priceLine 顏色。 */
const SL_COLOR = '#ef5350'
const TP_COLOR = '#26a69a'

/** ns 字串/數字 → epoch 秒(LWC UTCTimestamp)。 */
function nsToSec(ts: string | number): number {
  return Math.floor(Number(ts) / NS_PER_SEC)
}

/** 與 LWC SeriesMarker 對齊的最小規格。 */
export interface MarkerSpec {
  time: number
  position: 'aboveBar' | 'belowBar'
  shape: 'arrowUp' | 'arrowDown'
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
