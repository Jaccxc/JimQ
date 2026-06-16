/**
 * 卡 C — 行為測試:BacktestView 改為單一主圖版面。
 *
 * 驗:
 * - 不再有會混入 live 的中間 CandleChart(candle-chart testid 不存在)。
 * - 主圖 = RunExplorer 的單一 ReplayChart(run-explorer / replay-chart 存在)。
 * - 按 Run 啟動 → 連 scope=backtest 串流(URL 帶 scope=backtest),
 *   新回測串進主圖即時長出(live market bars 餵進主圖 ReplayChart)。
 *
 * mock chartController(攔截命令式呼叫)與 launcher/api;只驗 BacktestView 對外
 * 可觀察行為,不驗 LWC 內部。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'

const calls = {
  updateBar: vi.fn(),
  setHistory: vi.fn(),
  setMarkers: vi.fn(),
  clearPriceLines: vi.fn(),
  addPriceLine: vi.fn(),
  setEquityLine: vi.fn(),
  clearEquityLine: vi.fn(),
  reset: vi.fn(),
  fit: vi.fn(),
  destroy: vi.fn(),
}
vi.mock('@/lib/chartController', () => ({
  ChartController: vi.fn().mockImplementation(() => calls),
}))

// 攔截 WS:記錄連線 URL。
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

import BacktestView from '@/views/BacktestView.vue'
import { useMarketStore } from '@/stores/market'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000
function bar(time: number): BarDTO {
  return { ts: time * NS, time, open: '1', high: '2', low: '0', close: '1', volume: '1' }
}

beforeEach(() => {
  setActivePinia(createPinia())
  for (const fn of Object.values(calls)) fn.mockClear()
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
})

function mountView() {
  return mount(BacktestView, {
    props: {
      explorerApi: {
        fetchBacktestRuns: vi.fn().mockResolvedValue([]),
        fetchTrades: vi.fn().mockResolvedValue([]),
        fetchBars: vi.fn().mockResolvedValue([]),
      },
      // 注入 bars REST(掛載時 reload 用),避免打真網路。
      fetchBars: vi.fn().mockResolvedValue([]),
    },
  })
}

describe('BacktestView 單一主圖版面', () => {
  it('不再有會混入 live 的中間 CandleChart', async () => {
    const w = mountView()
    await flushPromises()
    expect(w.find('[data-testid="candle-chart"]').exists()).toBe(false)
  })

  it('主圖 = RunExplorer 的單一 ReplayChart', async () => {
    const w = mountView()
    await flushPromises()
    expect(w.find('[data-testid="run-explorer"]').exists()).toBe(true)
    expect(w.find('[data-testid="replay-chart"]').exists()).toBe(true)
  })

  it('掛載時連 scope=backtest 串流(主圖收 backtest 事件,不混 live)', async () => {
    mountView()
    await flushPromises()
    expect(FakeWebSocket.instances.some((ws) => ws.url.includes('scope=backtest'))).toBe(true)
  })

  it('未選 run 時,串流進來的 market bars 餵進主圖(即時長出)', async () => {
    const w = mountView()
    await flushPromises()
    calls.setHistory.mockClear()
    // 模擬 scope=backtest 串流把 bar 推進 **backtest 命名空間** market store
    // (真 bug 修復:BacktestView 主圖讀 'backtest' 命名空間,與 live 隔離)。
    const market = useMarketStore('backtest')
    market.setHistory([bar(1704067200), bar(1704070800)])
    await flushPromises()
    // 主圖(ReplayChart)以 backtest 串流 bars 重畫(setHistory 收到串流的 2 根)。
    const last = calls.setHistory.mock.calls.at(-1)
    expect(last).toBeTruthy()
    expect(last![0]).toHaveLength(2)
  })

  it('隔離:推進 live 命名空間 bars 不會餵進 backtest 主圖(真 bug 修復)', async () => {
    mountView()
    await flushPromises()
    const sinceLive = calls.setHistory.mock.calls.length
    // 往 'live' 命名空間灌 bars(模擬 Live 頁串流)→ 不該驅動 backtest 主圖重畫。
    useMarketStore('live').setHistory([bar(1704067200), bar(1704070800), bar(1704074400)])
    await flushPromises()
    expect(calls.setHistory.mock.calls.length).toBe(sinceLive)
  })
})
