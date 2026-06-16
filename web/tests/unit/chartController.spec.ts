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
  const chart = {
    addSeries: vi.fn((def: { _kind?: string }) => {
      const s = mkSeries(def?._kind ?? 'unknown')
      series.push(s)
      return s
    }),
    removeSeries: vi.fn((s: FakeSeries) => {
      removedSeries.push(s)
    }),
    timeScale: () => ({ fitContent: vi.fn() }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  }
  return { chart, series, removedSeries }
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
