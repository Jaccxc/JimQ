/**
 * 行為測試:useTradeSocket — WS 連線/重連/last_seq 補洞/信封分派整合。
 *
 * 用可注入的 FakeWebSocket + 假計時器,驗:
 * - 連線 URL 帶 channels;重連時帶 last_seq=最後看到的 seq。
 * - 收到信封 → 分派到 store(透過 connection.lastSeq 觀察)。
 * - close → 指數退避後重連(attempt 遞增)。
 * - 收到 live → status=live、reconnectAttempts 歸零。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTradeSocket } from '@/composables/useTradeSocket'
import { useConnectionStore } from '@/stores/connection'
import { useMarketStore } from '@/stores/market'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static OPEN = 1
  static CLOSED = 3
  url: string
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  sent: string[] = []
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  // 測試驅動。
  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }
  emit(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) })
  }
  close() {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.()
  }
  send(s: string) {
    this.sent.push(s)
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  FakeWebSocket.instances = []
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

function makeSocket() {
  return useTradeSocket({
    url: 'ws://x/ws/stream',
    channels: ['bars', 'orders', 'fills', 'positions', 'pnl'],
    WebSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    rng: () => 0, // 抽掉 jitter,讓退避決定論。
  })
}

describe('useTradeSocket 連線', () => {
  it('connect 建立 WS,URL 帶 channels;首次無 last_seq', () => {
    const sock = makeSocket()
    sock.connect()
    const ws = FakeWebSocket.instances[0]
    expect(ws.url).toContain('channels=bars')
    expect(ws.url).not.toContain('last_seq')
    sock.disconnect()
  })

  it('open → connection.status=connecting→connected', () => {
    const sock = makeSocket()
    sock.connect()
    FakeWebSocket.instances[0].open()
    expect(useConnectionStore().status).toBe('connected')
    sock.disconnect()
  })

  it('收到 bars 信封 → market store 更新 + lastSeq', () => {
    const sock = makeSocket()
    sock.connect()
    const ws = FakeWebSocket.instances[0]
    ws.open()
    ws.emit({
      channel: 'bars',
      seq: 42,
      data: { type: 'Bar', ts: 1700000000e9, time: 1700000000, open: '1', high: '2', low: '0.5', close: '1.5', volume: '1' },
    })
    expect(useMarketStore().bars).toHaveLength(1)
    expect(useConnectionStore().lastSeq).toBe(42)
    sock.disconnect()
  })

  it('收到 live → status=live 且 reconnectAttempts 歸零', () => {
    const sock = makeSocket()
    sock.connect()
    const ws = FakeWebSocket.instances[0]
    ws.open()
    useConnectionStore().incReconnect()
    ws.emit({ type: 'live' })
    expect(useConnectionStore().status).toBe('live')
    expect(useConnectionStore().reconnectAttempts).toBe(0)
    sock.disconnect()
  })
})

describe('useTradeSocket 重連 + last_seq 補洞', () => {
  it('close 後退避重連,attempt 遞增,新連線帶 last_seq=最後 seq', () => {
    const sock = makeSocket()
    sock.connect()
    const ws0 = FakeWebSocket.instances[0]
    ws0.open()
    ws0.emit({
      channel: 'bars',
      seq: 7,
      data: { type: 'Bar', ts: 1700000000e9, time: 1700000000, open: '1', high: '2', low: '0.5', close: '1.5', volume: '1' },
    })
    // 斷線。
    ws0.close()
    expect(useConnectionStore().reconnectAttempts).toBe(1)
    expect(useConnectionStore().status).toBe('connecting')
    // 推進退避計時器(base=500ms,jitter=0)。
    vi.advanceTimersByTime(500)
    const ws1 = FakeWebSocket.instances[1]
    expect(ws1).toBeTruthy()
    // 重連 URL 帶 last_seq=7 補洞。
    expect(ws1.url).toContain('last_seq=7')
    sock.disconnect()
  })

  it('連續斷線退避指數成長(attempt 2 在 1000ms 後才重連)', () => {
    const sock = makeSocket()
    sock.connect()
    FakeWebSocket.instances[0].open()
    FakeWebSocket.instances[0].close() // attempt 1, delay 500
    vi.advanceTimersByTime(500)
    FakeWebSocket.instances[1].close() // attempt 2, delay 1000
    expect(useConnectionStore().reconnectAttempts).toBe(2)
    // 還沒到 1000ms 不應有新連線。
    vi.advanceTimersByTime(500)
    expect(FakeWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(500)
    expect(FakeWebSocket.instances).toHaveLength(3)
    sock.disconnect()
  })

  it('disconnect 後 close 不再重連', () => {
    const sock = makeSocket()
    sock.connect()
    FakeWebSocket.instances[0].open()
    sock.disconnect()
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })
})
