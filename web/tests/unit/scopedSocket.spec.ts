/**
 * 卡 A — Live/Backtest 資料源隔離(前端):useTradeSocket 帶 scope。
 *
 * 行為:WS 連線 URL 帶 ``scope`` query,讓 gateway 路由到對應 scope 的 hub
 * (api 雙 scope 並行消費)。LiveView 用 scope=live、BacktestView 用 scope=backtest
 * → Live 分頁的 WS 只收 live hub 事件,不混入 backtest。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTradeSocket } from '@/composables/useTradeSocket'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  url: string
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  close() {
    this.onclose = null
  }
  send() {}
}

beforeEach(() => {
  setActivePinia(createPinia())
  FakeWebSocket.instances = []
})

function makeSocket(scope?: string) {
  return useTradeSocket({
    url: 'ws://x/ws/stream',
    channels: ['bars'],
    scope,
    WebSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    rng: () => 0,
  })
}

describe('useTradeSocket scope', () => {
  it('scope=backtest → URL 帶 scope=backtest', () => {
    const sock = makeSocket('backtest')
    sock.connect()
    expect(FakeWebSocket.instances[0].url).toContain('scope=backtest')
    sock.disconnect()
  })

  it('scope=live → URL 帶 scope=live', () => {
    const sock = makeSocket('live')
    sock.connect()
    expect(FakeWebSocket.instances[0].url).toContain('scope=live')
    sock.disconnect()
  })

  it('未指定 scope → URL 不帶 scope(相容,gateway 預設 live)', () => {
    const sock = makeSocket()
    sock.connect()
    expect(FakeWebSocket.instances[0].url).not.toContain('scope=')
    sock.disconnect()
  })
})
