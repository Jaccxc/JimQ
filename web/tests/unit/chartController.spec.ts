/**
 * 行為測試:ChartController EMA line series 管理 + reset(切換安全)。
 *
 * 用注入的 fake chart factory(模擬 LWC v5 IChartApi/ISeriesApi 子集)驗:
 * - setEmaLine(id, points):首次建 line series 並 setData;再次同 id → 更新同一個
 *   series(不重複建,避免記憶體洩漏/重複 series)。
 * - removeEmaLine(id):移除對應 line series。
 * - reset():清掉 candlestick 資料、所有 EMA line series、markers、priceLines,
 *   但不重建 chart(切換標的時重用 chart 實例)。
 *
 * 只驗行為(public interface 對 fake 的呼叫序),不驗 LWC 內部實作。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ChartController } from '@/lib/chartController'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000
function bar(time: number, close: number): BarDTO {
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

interface FakeSeries {
  kind: string
  setData: ReturnType<typeof vi.fn>
  update: ReturnType<typeof vi.fn>
  createPriceLine: ReturnType<typeof vi.fn>
  removePriceLine: ReturnType<typeof vi.fn>
}

function makeFakeChart() {
  const series: FakeSeries[] = []
  const removedSeries: FakeSeries[] = []
  function mkSeries(kind: string): FakeSeries {
    return {
      kind,
      setData: vi.fn(),
      update: vi.fn(),
      createPriceLine: vi.fn(() => ({})),
      removePriceLine: vi.fn(),
    }
  }
  // 單一 timeScale 物件(跨呼叫穩定),便於斷言 fitContent / setVisibleLogicalRange。
  const timeScaleApi = {
    fitContent: vi.fn(),
    setVisibleLogicalRange: vi.fn(),
    applyOptions: vi.fn(),
  }
  const chart = {
    addSeries: vi.fn((def: { _kind?: string }) => {
      const s = mkSeries(def?._kind ?? 'unknown')
      series.push(s)
      return s
    }),
    removeSeries: vi.fn((s: FakeSeries) => {
      removedSeries.push(s)
    }),
    timeScale: () => timeScaleApi,
    priceScale: () => ({ applyOptions: vi.fn() }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  }
  return { chart, series, removedSeries, timeScaleApi }
}

function makeController() {
  const fake = makeFakeChart()
  const deps = {
    createChart: vi.fn(() => fake.chart),
    candlestickSeriesDef: { _kind: 'candle' },
    lineSeriesDef: { _kind: 'line' },
    createSeriesMarkers: vi.fn(() => ({ setMarkers: vi.fn() })),
  }
  const ctrl = new ChartController({} as unknown as HTMLElement, deps as never)
  return { ctrl, fake }
}

describe('ChartController EMA line series', () => {
  it('setEmaLine 首次建 line series 並 setData', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEmaLine('fast', [{ time: 100, value: 1 } as never])
    const lines = fake.series.filter((s) => s.kind === 'line')
    expect(lines).toHaveLength(1)
    expect(lines[0].setData).toHaveBeenCalledTimes(1)
  })

  it('setEmaLine 同 id 第二次 → 更新同一 series,不重複建(防記憶體洩漏)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEmaLine('fast', [{ time: 100, value: 1 } as never])
    ctrl.setEmaLine('fast', [{ time: 160, value: 2 } as never])
    const lines = fake.series.filter((s) => s.kind === 'line')
    expect(lines).toHaveLength(1) // 仍只有一個 line series。
    expect(lines[0].setData).toHaveBeenCalledTimes(2)
  })

  it('不同 id 各自建獨立 line series', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEmaLine('fast', [])
    ctrl.setEmaLine('slow', [])
    expect(fake.series.filter((s) => s.kind === 'line')).toHaveLength(2)
  })

  it('removeEmaLine 移除對應 line series', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEmaLine('fast', [])
    ctrl.removeEmaLine('fast')
    expect(fake.chart.removeSeries).toHaveBeenCalledTimes(1)
    // 再 set 同 id → 重新建立。
    ctrl.setEmaLine('fast', [])
    expect(fake.series.filter((s) => s.kind === 'line')).toHaveLength(2)
  })
})

describe('ChartController updateBar 單調守衛(reconnect/亂序安全)', () => {
  it('updateBar 套用新 time / 同 time(重畫最後一根)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1)])
    const candle = fake.series.find((s) => s.kind === 'candle')!
    ctrl.updateBar(bar(160, 2)) // 新 time
    ctrl.updateBar(bar(160, 3)) // 同 time 覆寫(最後一根仍可更新)
    expect(candle.update).toHaveBeenCalledTimes(2)
  })

  it('updateBar 丟棄嚴格較舊的 time(避免 LWC "update oldest" 拋錯)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1), bar(200, 2)])
    const candle = fake.series.find((s) => s.kind === 'candle')!
    candle.update.mockClear()
    ctrl.updateBar(bar(150, 9)) // 比已知最後 time(200)舊 → 丟棄,不呼叫 update
    expect(candle.update).not.toHaveBeenCalled()
  })

  it('setHistory 重設單調游標(重載較舊歷史後可再串流)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(500, 1)]) // 高 time
    ctrl.setHistory([bar(100, 1)]) // 重載到較舊歷史(切標的/重連)
    const candle = fake.series.find((s) => s.kind === 'candle')!
    candle.update.mockClear()
    ctrl.updateBar(bar(160, 2)) // 相對新歷史(100)是較新 → 應套用
    expect(candle.update).toHaveBeenCalledTimes(1)
  })
})

describe('ChartController reset(切換標的安全)', () => {
  it('reset 清 candlestick 資料與所有 EMA line,但不重建 chart', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1), bar(160, 2)])
    ctrl.setEmaLine('fast', [])
    ctrl.setEmaLine('slow', [])
    ctrl.reset()
    // chart 實例不重建。
    expect(fake.chart.remove).not.toHaveBeenCalled()
    // 兩條 EMA line 被移除。
    expect(fake.chart.removeSeries).toHaveBeenCalledTimes(2)
    // candlestick series 用空資料清空(reset 後可再 setHistory)。
    const candle = fake.series.find((s) => s.kind === 'candle')!
    expect(candle.setData).toHaveBeenLastCalledWith([])
  })

  it('reset 後 setEmaLine 同 id 重新建立(狀態已清)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEmaLine('fast', [])
    ctrl.reset()
    ctrl.setEmaLine('fast', [])
    // reset 移除 1 次,之後重新建立一個新 line。
    expect(fake.series.filter((s) => s.kind === 'line')).toHaveLength(2)
    expect(fake.chart.removeSeries).toHaveBeenCalledTimes(1)
  })
})

describe('ChartController 預設縮放窗(問題3:≥70 根 + 右側 ~20% 空白)', () => {
  it('setHistory 用 setVisibleLogicalRange(非 fitContent)套預設窗', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1), bar(160, 2)])
    expect(fake.timeScaleApi.setVisibleLogicalRange).toHaveBeenCalledTimes(1)
    // setHistory 不再 blind fitContent(那會把 2 根放大成超大蠟燭)。
    expect(fake.timeScaleApi.fitContent).not.toHaveBeenCalled()
  })

  it('視窗至少 70 根寬,且右端在最後一根之後留白(僅 2 根時不放大)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1), bar(160, 2)]) // 只有 2 根
    const { from, to } = fake.timeScaleApi.setVisibleLogicalRange.mock.calls[0][0]
    // 窗寬 ≥ 70 根。
    expect(to - from).toBeGreaterThanOrEqual(70)
    // 右側留白:右端超過最後一根(index 1),約 20% 窗寬。
    const lastIndex = 1
    expect(to).toBeGreaterThan(lastIndex)
    expect(to - lastIndex).toBeGreaterThanOrEqual(70 * 0.2 - 1)
  })

  it('updateBar 新增 bar 時視窗向右捲動(維持窗寬),同 time 覆寫不重套', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1)]) // 1 次
    fake.timeScaleApi.setVisibleLogicalRange.mockClear()
    ctrl.updateBar(bar(160, 2)) // 新 time → append → 重套窗
    ctrl.updateBar(bar(160, 3)) // 同 time 覆寫 → 不重套
    expect(fake.timeScaleApi.setVisibleLogicalRange).toHaveBeenCalledTimes(1)
    const last = fake.timeScaleApi.setVisibleLogicalRange.mock.calls.at(-1)![0]
    expect(last.to - last.from).toBeGreaterThanOrEqual(70)
  })

  it('fit()(Fit 按鈕)維持 fitContent 全部資料語意(不被預設窗取代)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setHistory([bar(100, 1), bar(160, 2)])
    ctrl.fit()
    expect(fake.timeScaleApi.fitContent).toHaveBeenCalledTimes(1)
  })
})
