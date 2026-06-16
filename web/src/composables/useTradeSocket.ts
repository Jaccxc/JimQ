/**
 * useTradeSocket — 管理單一多工 WS 連線、重連、last_seq 補洞、信封分派。
 *
 * 設計(對齊 gateway api/src/app/ws/stream.py):
 * - connect():開 WS,query 帶 channels;若 connection.lastSeq>0 帶 last_seq 補洞。
 * - onmessage:JSON.parse → dispatchMessage(路由到 stores、更新 lastSeq)。
 * - onclose(非主動斷):指數退避 + jitter(nextBackoffMs)後重連,attempt 遞增。
 * - 收到 {type:"live"}:reconnectAttempts 歸零(連線穩定)。
 * - disconnect():主動關閉,停止重連。
 *
 * 依賴注入(WebSocketCtor/rng/setTimeout)以利單元測試決定論。
 * WS 實例與計時器存在 closure(非 Vue 響應式)。
 */
import { nextBackoffMs } from '@/lib/backoff'
import { dispatchMessage } from '@/composables/dispatch'
import { useConnectionStore } from '@/stores/connection'
import type { WsMessage } from '@/types/contract'

export interface TradeSocketOptions {
  /** WS 端點(預設同源 /ws/stream)。 */
  url?: string
  /** 要訂的 channel。 */
  channels: string[]
  /**
   * 卡 A:資料源 scope(``live`` / ``backtest``)。gateway 依此路由到對應 scope
   * 的 hub(api 雙 scope 並行消費)→ Live 分頁只收 live 事件,不混入 backtest。
   * 省略時不帶 scope query,gateway 預設 live(相容)。
   */
  scope?: string
  /** 心跳間隔秒(帶給 gateway query)。 */
  heartbeatS?: number
  /** 注入 WebSocket 建構子(測試用)。 */
  WebSocketCtor?: typeof WebSocket
  /** 注入 jitter rng(測試用)。 */
  rng?: () => number
}

export interface TradeSocket {
  connect: () => void
  disconnect: () => void
}

function defaultUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/stream`
}

export function useTradeSocket(opts: TradeSocketOptions): TradeSocket {
  const WS = opts.WebSocketCtor ?? WebSocket
  const rng = opts.rng ?? Math.random
  const baseUrl = opts.url ?? defaultUrl()

  let ws: WebSocket | null = null
  let stopped = false
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function buildUrl(): string {
    const conn = useConnectionStore()
    const params = new URLSearchParams()
    params.set('channels', opts.channels.join(','))
    if (opts.scope) params.set('scope', opts.scope)
    if (opts.heartbeatS != null) params.set('heartbeat_s', String(opts.heartbeatS))
    // 重連補洞:帶上目前已知最後 seq。
    if (conn.lastSeq > 0) params.set('last_seq', String(conn.lastSeq))
    return `${baseUrl}?${params.toString()}`
  }

  function scheduleReconnect() {
    if (stopped) return
    const conn = useConnectionStore()
    conn.incReconnect()
    conn.setStatus('connecting')
    const delay = nextBackoffMs(conn.reconnectAttempts - 1, rng)
    reconnectTimer = setTimeout(() => open(), delay)
  }

  function open() {
    const conn = useConnectionStore()
    conn.setStatus('connecting')
    ws = new WS(buildUrl())
    ws.onopen = () => {
      useConnectionStore().setStatus('connected')
    }
    ws.onmessage = (e: MessageEvent) => {
      let msg: WsMessage
      try {
        msg = JSON.parse(e.data as string)
      } catch {
        return
      }
      // 帶 scope → 路由到對應命名空間 store(Live/Backtest 互不污染)。
      dispatchMessage(msg, opts.scope ?? 'live')
      // live 分界:連線穩定,歸零退避計數。
      if ((msg as { type?: string }).type === 'live') {
        useConnectionStore().resetReconnect()
      }
    }
    ws.onclose = () => {
      ws = null
      if (!stopped) scheduleReconnect()
    }
    ws.onerror = () => {
      // 錯誤後通常會觸發 close;不額外處理。
    }
  }

  function connect() {
    stopped = false
    open()
  }

  function disconnect() {
    stopped = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    const conn = useConnectionStore()
    conn.setStatus('disconnected')
    if (ws) {
      ws.onclose = null // 避免主動關觸發重連。
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      ws = null
    }
  }

  return { connect, disconnect }
}
