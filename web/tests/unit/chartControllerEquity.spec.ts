/**
 * 卡 C — 行為測試:ChartController 權益曲線副圖(主圖下方獨立 pane 的 line series)。
 *
 * - setEquityLine(points):首次在獨立 pane(paneIndex 1)建 line series 並 setData;
 *   再次呼叫 → 更新同一 series(不重複建,換 run 重畫不洩漏)。
 * - clearEquityLine():移除權益 line series。
 * - reset():連同權益副圖一起清掉(切標的/換 run 安全)。
 *
 * 只驗 public interface 對 fake LWC 的呼叫(不驗 LWC 內部)。
 */
import { describe, it, expect, vi } from 'vitest'
import { ChartController } from '@/lib/chartController'

interface FakeSeries {
  kind: string
  paneIndex: number | undefined
  setData: ReturnType<typeof vi.fn>
}

function makeFakeChart() {
  const series: FakeSeries[] = []
  const removedSeries: FakeSeries[] = []
  const chart = {
    addSeries: vi.fn((def: { _kind?: string }, _opts?: unknown, paneIndex?: number) => {
      const s: FakeSeries = {
        kind: def?._kind ?? 'unknown',
        paneIndex,
        setData: vi.fn(),
        update: vi.fn(),
        createPriceLine: vi.fn(() => ({})),
        removePriceLine: vi.fn(),
      } as unknown as FakeSeries
      series.push(s)
      return s
    }),
    removeSeries: vi.fn((s: FakeSeries) => removedSeries.push(s)),
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

const pts = [
  { time: 100, value: 10 },
  { time: 200, value: 25 },
]

describe('ChartController 權益副圖', () => {
  it('setEquityLine 在獨立 pane(index 1)建 line series 並 setData', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEquityLine(pts)
    const eq = fake.series.filter((s) => s.kind === 'line')
    expect(eq).toHaveLength(1)
    expect(eq[0].paneIndex).toBe(1) // 主圖(K 線)在 pane 0,權益在 pane 1。
    expect(eq[0].setData).toHaveBeenCalledWith(pts)
  })

  it('setEquityLine 第二次 → 更新同一 series,不重複建(換 run 重畫不洩漏)', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEquityLine(pts)
    ctrl.setEquityLine([{ time: 300, value: 5 }])
    const eq = fake.series.filter((s) => s.kind === 'line')
    expect(eq).toHaveLength(1)
    expect(eq[0].setData).toHaveBeenCalledTimes(2)
  })

  it('clearEquityLine 移除權益 line series', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEquityLine(pts)
    ctrl.clearEquityLine()
    expect(fake.chart.removeSeries).toHaveBeenCalledTimes(1)
    // 再 set → 重新建立。
    ctrl.setEquityLine(pts)
    expect(fake.series.filter((s) => s.kind === 'line')).toHaveLength(2)
  })

  it('reset 連同權益副圖一起清掉', () => {
    const { ctrl, fake } = makeController()
    ctrl.setEquityLine(pts)
    ctrl.reset()
    expect(fake.chart.removeSeries).toHaveBeenCalledTimes(1)
    // reset 後再 set → 重新建立(狀態已清)。
    ctrl.setEquityLine(pts)
    expect(fake.series.filter((s) => s.kind === 'line')).toHaveLength(2)
  })
})
