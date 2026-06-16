/**
 * 後端契約型別(對齊 jimq_core.schemas + WS gateway #7 + bars REST #8)。
 *
 * 真相來源:
 * - libs/jimq_core/jimq_core/schemas.py(BarDTO / StreamEnvelope / Channel)
 * - api/src/app/ws/stream.py(信封流:補洞 → 快照(snapshot:true)→ {type:"live"} → delta;心跳 {type:"heartbeat"})
 * - api/src/app/services/nautilus_consumer.py(orders/fills/positions/pnl 的 data 為 Nautilus 純量 dict,帶 type)
 *
 * 理想上應由 FastAPI OpenAPI 生成;但 BarDTO/StreamEnvelope 之外的事件 data
 * 是 Nautilus 透傳 dict(OpenAPI 只描述到 dict[str, Any]),故這裡以實測 payload
 * 形狀(api/tests/test_nautilus_consumer.py)補齊前端友善型別。詳見 docs。
 */

/** WS 多工 channel 名稱(共用契約)。 */
export type Channel = 'bars' | 'trades' | 'orders' | 'fills' | 'positions' | 'pnl'

/** 單根 K 線傳輸物件(Lightweight Charts 對齊)。OHLCV 以字串保留交易所精度。 */
export interface BarDTO {
  /** epoch 奈秒(Nautilus ts_init),保留全精度。 */
  ts: number
  /** epoch 秒(Lightweight Charts UTCTimestamp)。 */
  time: number
  open: string
  high: string
  low: string
  close: string
  volume: string
}

/** WS 串流信封共用契約 {channel, seq, data}。 */
export interface StreamEnvelope {
  channel: Channel
  seq: number
  data: Record<string, unknown>
  /** 快照階段的信封帶 snapshot:true(gateway 注入)。 */
  snapshot?: boolean
}

/** gateway 控制訊息:快照/補洞結束的 live 分界。 */
export interface LiveMarker {
  type: 'live'
}

/** gateway 閒置心跳。 */
export interface Heartbeat {
  type: 'heartbeat'
  ts: number
}

/** 從 WS 收到的任一訊息(信封或控制訊息)。 */
export type WsMessage = StreamEnvelope | LiveMarker | Heartbeat

export function isLiveMarker(m: WsMessage): m is LiveMarker {
  return (m as LiveMarker).type === 'live'
}

export function isHeartbeat(m: WsMessage): m is Heartbeat {
  return (m as Heartbeat).type === 'heartbeat'
}

export function isEnvelope(m: WsMessage): m is StreamEnvelope {
  return typeof (m as StreamEnvelope).channel === 'string'
}

// --- 事件 data 子型別(Nautilus 透傳,帶 type;以實測 payload 形狀為準)---

/**
 * 卡 B(Live 次秒 tick):TradeTick 逐筆成交 data(consumer 正規化補 time)。
 * 前端用 time(epoch 秒)+ price 聚合到形成中那根 1m K 線(⛔ 純視覺,不進策略)。
 */
export interface TradeData {
  type: 'TradeTick'
  /** epoch 秒(consumer 由 ts_init 補;對齊 LWC UTCTimestamp）。 */
  time: number
  /** 成交價(字串保留交易所精度;前端 parseFloat)。 */
  price: string
  [k: string]: unknown
}

export interface OrderInitializedData {
  type: 'OrderInitialized'
  instrument_id: string
  client_order_id: string
  order_side: 'BUY' | 'SELL'
  order_type: string // MARKET / LIMIT / STOP_MARKET ...
  quantity: string
  /** LIMIT(TP)價;bracket TP order 帶。 */
  price?: string
  /** STOP_MARKET(SL)觸發價;bracket SL order 帶。 */
  trigger_price?: string
  ts_init: string
  [k: string]: unknown
}

export interface OrderFilledData {
  type: 'OrderFilled'
  instrument_id: string
  client_order_id: string
  position_id: string
  order_side: 'BUY' | 'SELL'
  order_type: string
  last_qty: string
  last_px: string
  ts_init: string
  [k: string]: unknown
}

export interface PositionData {
  type: 'PositionOpened' | 'PositionChanged' | 'PositionClosed'
  instrument_id: string
  position_id: string
  /** 進場方向。 */
  entry: 'BUY' | 'SELL'
  /** LONG / FLAT / SHORT。 */
  side: 'LONG' | 'SHORT' | 'FLAT'
  signed_qty: number
  quantity: string
  last_px: string
  avg_px_open: number
  realized_pnl?: string
  ts_init: string
  [k: string]: unknown
}

export interface AccountBalance {
  total: string
  locked: string
  free: string
  currency: string
}

export interface AccountStateData {
  type: 'AccountState'
  account_id: string
  base_currency: string
  balances: AccountBalance[]
  ts_init: string
  [k: string]: unknown
}
