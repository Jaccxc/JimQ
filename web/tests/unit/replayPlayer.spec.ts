/**
 * Backtest 前端回放播放器 — 回放引擎(純邏輯)行為測試。
 *
 * useReplayPlayer 管理:全量 bars/markers/equity + currentIndex + playing + speed
 * (根/秒)。play 用 timer 依 speed 推進 index;每步把「到 currentIndex(對應
 * bar.time)為止」的 bars/markers/equity 增量餵進 sink(chart controller 的子集)。
 *
 * 效能:逐根用 sink.updateBar(append 一根)而非每 tick 重 setHistory 全量;
 * marker 用累積到當前 bar.time;equity 同步到當前 bar.time。
 *
 * 只驗行為(public interface 對 fake sink 的呼叫 + 對外暴露的狀態),不驗實作細節。
 * 用 fake timer 達決定論。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useReplayPlayer, type ReplaySink } from '@/composables/useReplayPlayer'
import type { BarDTO } from '@/types/contract'
import type { MarkerSpec } from '@/lib/tradeMapping'
import type { EquityPoint } from '@/lib/equityCurve'

const NS = 1_000_000_000
function bar(time: number, close = 1): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(close),
    high: String(close + 1),
    low: String(close - 1),
    close: String(close),
    volume: '1',
  }
}
function marker(time: number): MarkerSpec {
  return { time, position: 'belowBar', shape: 'arrowUp', color: '#26a69a', text: `@${time}` }
}
function eq(time: number, value: number): EquityPoint {
  return { time, value }
}

function makeSink(): ReplaySink & {
  appended: BarDTO[]
  markerCalls: MarkerSpec[][]
  equityCalls: EquityPoint[][]
  historyCalls: BarDTO[][]
  resetCount: number
  fitCount: number
} {
  const appended: BarDTO[] = []
  const markerCalls: MarkerSpec[][] = []
  const equityCalls: EquityPoint[][] = []
  const historyCalls: BarDTO[][] = []
  return {
    appended,
    markerCalls,
    equityCalls,
    historyCalls,
    resetCount: 0,
    fitCount: 0,
    updateBar(b: BarDTO) {
      appended.push(b)
    },
    setHistory(bars: BarDTO[]) {
      historyCalls.push(bars)
    },
    setMarkers(specs: MarkerSpec[]) {
      markerCalls.push([...specs])
    },
    setEquityLine(points: EquityPoint[]) {
      equityCalls.push([...points])
    },
    clearEquityLine() {
      this.equityCalls.push([])
    },
    reset() {
      this.resetCount += 1
    },
    fit() {
      this.fitCount += 1
    },
  }
}

// 5 根 bar、time 100/200/.../500;trade marker 在 200 與 400;equity 在 200、400。
const BARS = [bar(100), bar(200), bar(300), bar(400), bar(500)]
const MARKERS = [marker(200), marker(400)]
const EQUITY = [eq(200, 10), eq(400, 30)]

let sink: ReturnType<typeof makeSink>

beforeEach(() => {
  vi.useFakeTimers()
  sink = makeSink()
})
afterEach(() => {
  vi.useRealTimers()
})

describe('useReplayPlayer 載入與初始狀態', () => {
  it('load 後 total=bar 數、index=0、未播放、預設速度 5', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    expect(p.total.value).toBe(5)
    expect(p.currentIndex.value).toBe(0)
    expect(p.playing.value).toBe(false)
    expect(p.speed.value).toBe(5)
  })

  it('load 先 reset sink,並畫出第 0 根(只有第一根,無未來 marker/equity)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    // 至少畫到 index 0 的那一根。
    expect(sink.appended.map((b) => b.time)).toContain(100)
    // index 0(time=100)之前無 marker/equity → 累積為空。
    expect(sink.markerCalls.at(-1)).toEqual([])
    expect(sink.equityCalls.at(-1)).toEqual([])
  })
})

describe('useReplayPlayer 播放推進(fake timer)', () => {
  it('play 依 speed 每秒推進 speed 根:speed=1 時 1 秒推進 1 根', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    expect(p.playing.value).toBe(true)
    vi.advanceTimersByTime(1000) // 1 秒 → +1 根 → index 1(time=200)
    expect(p.currentIndex.value).toBe(1)
    vi.advanceTimersByTime(2000) // 再 2 秒 → index 3(time=400)
    expect(p.currentIndex.value).toBe(3)
  })

  it('逐根 append(updateBar)而非重畫全量(效能):推進到 index 2 時 appended 含 100/200/300', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(2)
    p.play()
    vi.advanceTimersByTime(1000) // +2 → index 2(time=300)
    expect(p.currentIndex.value).toBe(2)
    const times = sink.appended.map((b) => b.time)
    expect(times).toContain(100)
    expect(times).toContain(200)
    expect(times).toContain(300)
    expect(times).not.toContain(400)
  })

  it('marker/equity 累積到當前 bar.time(到 index 1=time200 → 含 200 那筆;不含 400)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    vi.advanceTimersByTime(1000) // index 1, time=200
    expect(sink.markerCalls.at(-1)!.map((m) => m.time)).toEqual([200])
    expect(sink.equityCalls.at(-1)!.map((e) => e.time)).toEqual([200])
    vi.advanceTimersByTime(2000) // index 3, time=400 → 含 200、400
    expect(sink.markerCalls.at(-1)!.map((m) => m.time)).toEqual([200, 400])
    expect(sink.equityCalls.at(-1)!.map((e) => e.time)).toEqual([200, 400])
  })

  it('播到結尾自動停(index=total-1 後 playing=false,不超界)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(10)
    p.play()
    vi.advanceTimersByTime(2000) // 遠超 5 根
    expect(p.currentIndex.value).toBe(4) // total-1
    expect(p.playing.value).toBe(false)
  })
})

describe('useReplayPlayer 暫停', () => {
  it('pause 後 index 不再推進(timer 清掉)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    vi.advanceTimersByTime(1000) // index 1
    p.pause()
    expect(p.playing.value).toBe(false)
    vi.advanceTimersByTime(5000) // 暫停後不動
    expect(p.currentIndex.value).toBe(1)
  })

  it('暫停後再 play 可繼續推進', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    vi.advanceTimersByTime(1000)
    p.pause()
    p.play()
    vi.advanceTimersByTime(1000)
    expect(p.currentIndex.value).toBe(2)
  })
})

describe('useReplayPlayer scrub(可往回/往前拖)', () => {
  it('scrub 到較前 index → 重建到該 index(reset + 重畫切片),index 正確', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    vi.advanceTimersByTime(3000) // index 3
    p.pause()
    p.scrub(1) // 往回到 index 1
    expect(p.currentIndex.value).toBe(1)
    // 切片正確:marker/equity 累積到 time=200。
    expect(sink.markerCalls.at(-1)!.map((m) => m.time)).toEqual([200])
    expect(sink.equityCalls.at(-1)!.map((e) => e.time)).toEqual([200])
  })

  it('scrub 往前到較後 index → 補畫到該 index,marker 累積到該 time', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.scrub(3) // 直接拖到 index 3(time=400)
    expect(p.currentIndex.value).toBe(3)
    expect(sink.markerCalls.at(-1)!.map((m) => m.time)).toEqual([200, 400])
    const times = sink.appended.map((b) => b.time)
    expect(times).toContain(400)
    expect(times).not.toContain(500)
  })

  it('scrub 夾在 [0, total-1] 範圍內', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.scrub(99)
    expect(p.currentIndex.value).toBe(4)
    p.scrub(-5)
    expect(p.currentIndex.value).toBe(0)
  })
})

describe('useReplayPlayer 重播 / 跳結尾', () => {
  it('replay 把 index 歸 0 並從頭(reset)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(2)
    p.play()
    vi.advanceTimersByTime(2000)
    p.replay()
    expect(p.currentIndex.value).toBe(0)
    expect(sink.markerCalls.at(-1)).toEqual([])
    expect(sink.equityCalls.at(-1)).toEqual([])
  })

  it('replay 後即自動播放(可暫停)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.replay()
    expect(p.playing.value).toBe(true)
    vi.advanceTimersByTime(1000)
    expect(p.currentIndex.value).toBe(1)
  })

  it('toEnd 一次畫完整(setHistory 全量 + 全部 marker + 全部 equity),index=total-1,停', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    p.toEnd()
    expect(p.currentIndex.value).toBe(4)
    expect(p.playing.value).toBe(false)
    // 一次性畫法:setHistory 收到全量 5 根。
    expect(sink.historyCalls.at(-1)).toHaveLength(5)
    expect(sink.markerCalls.at(-1)!.map((m) => m.time)).toEqual([200, 400])
    expect(sink.equityCalls.at(-1)!.map((e) => e.time)).toEqual([200, 400])
  })
})

describe('useReplayPlayer setSpeed', () => {
  it('setSpeed 夾在 1~50', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(0)
    expect(p.speed.value).toBe(1)
    p.setSpeed(999)
    expect(p.speed.value).toBe(50)
    p.setSpeed(20)
    expect(p.speed.value).toBe(20)
  })

  it('播放中改速度即時生效(下一 tick 用新速度)', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: BARS, markers: MARKERS, equity: EQUITY })
    p.setSpeed(1)
    p.play()
    vi.advanceTimersByTime(1000) // index 1
    p.setSpeed(2)
    vi.advanceTimersByTime(1000) // +2 → index 3
    expect(p.currentIndex.value).toBe(3)
  })
})

describe('useReplayPlayer 空資料安全', () => {
  it('load 空 bars 不爆,total=0、index=0、play 無效', () => {
    const p = useReplayPlayer(sink)
    p.load({ bars: [], markers: [], equity: [] })
    expect(p.total.value).toBe(0)
    expect(p.currentIndex.value).toBe(0)
    p.play()
    vi.advanceTimersByTime(2000)
    expect(p.playing.value).toBe(false)
  })
})
