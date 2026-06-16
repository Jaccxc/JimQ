/**
 * Lightweight Charts v5 命令式控制器(置於 Vue 響應式之外)。
 *
 * 鐵律(研究 frontend-viz §1/§5):chart/series 實例**不放 reactive/ref**,
 * 放普通變數,命令式更新。本控制器是純 TS class,由元件在 onMounted 建立並
 * 持於非響應式變數(markRaw / 普通 let),watcher/socket handler 命令式呼叫。
 *
 * 對齊 LWC v5 API:
 * - createChart(container, options)
 * - chart.addSeries(CandlestickSeries, options)  // v5 改用 series 定義
 * - createSeriesMarkers(series, markers)          // v5 marker 改獨立函式
 * - series.setData / series.update                 // 初始/即時
 * - series.createPriceLine(options) / removePriceLine
 * - chart.applyOptions({ attributionLogo: true }) // TradingView 標註(授權要求)
 */
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  createSeriesMarkers,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type IPriceLine,
  type CandlestickData,
  type LineData,
  type SeriesMarker,
  type UTCTimestamp,
  type Time,
} from 'lightweight-charts'
import type { BarDTO } from '@/types/contract'
import type { LinePoint } from '@/lib/ema'
import type { MarkerSpec, PriceLineSpec } from '@/lib/tradeMapping'

/**
 * 可注入相依(測試用 fake LWC API)。預設綁真實 lightweight-charts。
 * 對齊 LWC v5:createChart、series 定義(addSeries(def))、createSeriesMarkers。
 */
export interface ChartDeps {
  createChart: typeof createChart
  candlestickSeriesDef: unknown
  lineSeriesDef: unknown
  createSeriesMarkers: typeof createSeriesMarkers
}

const DEFAULT_DEPS: ChartDeps = {
  createChart,
  candlestickSeriesDef: CandlestickSeries,
  lineSeriesDef: LineSeries,
  createSeriesMarkers,
}

/** EMA line series 預設顏色(fast 偏藍、slow 偏橘)。 */
const EMA_COLORS: Record<string, string> = {
  fast: '#42a5f5',
  slow: '#ffa726',
}

function toCandle(b: BarDTO): CandlestickData<Time> {
  return {
    time: b.time as UTCTimestamp,
    open: Number(b.open),
    high: Number(b.high),
    low: Number(b.low),
    close: Number(b.close),
  }
}

function toMarker(m: MarkerSpec): SeriesMarker<Time> {
  return {
    time: m.time as UTCTimestamp,
    position: m.position,
    shape: m.shape,
    color: m.color,
    text: m.text,
  }
}

export class ChartController {
  private chart: IChartApi
  private series: ISeriesApi<'Candlestick'>
  private markersApi: ISeriesMarkersPluginApi<Time>
  private markers: SeriesMarker<Time>[] = []
  /** priceLine id → handle,便於去重/移除。 */
  private priceLines = new Map<string, IPriceLine>()
  /** EMA line series:id(fast/slow)→ series handle,重用避免重複建。 */
  private emaLines = new Map<string, ISeriesApi<'Line'>>()
  /** 已套用的最後一根 bar time(單調守衛:丟棄較舊更新,避免 LWC 拋
   * "Cannot update oldest data";reconnect/切標的重載較舊歷史後由 setHistory 重設)。 */
  private lastBarTime: number | null = null
  private deps: ChartDeps

  constructor(container: HTMLElement, deps: ChartDeps = DEFAULT_DEPS) {
    this.deps = deps
    this.chart = deps.createChart(container, {
      layout: {
        background: { color: '#0e1117' },
        textColor: '#d1d4dc',
        // TradingView 標註(Apache-2.0 授權要求):on-chart attribution logo。
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: '#1c2230' },
        horzLines: { color: '#1c2230' },
      },
      autoSize: true,
      timeScale: { timeVisible: true, secondsVisible: false },
    })
    this.series = this.chart.addSeries(deps.candlestickSeriesDef as never, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    })
    this.markersApi = deps.createSeriesMarkers(this.series, [])
  }

  /**
   * 疊加 / 更新 EMA line series(id 為 'fast'/'slow' 等)。
   * 首次建立 line series;之後同 id 重用同一 series 命令式 setData,
   * 避免重複建 series 造成記憶體洩漏。
   */
  setEmaLine(id: string, points: LinePoint[]): void {
    let line = this.emaLines.get(id)
    if (!line) {
      line = this.chart.addSeries(this.deps.lineSeriesDef as never, {
        color: EMA_COLORS[id] ?? '#b0bec5',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      }) as ISeriesApi<'Line'>
      this.emaLines.set(id, line)
    }
    line.setData(points as unknown as LineData<Time>[])
  }

  /** 移除指定 EMA line series(關閉疊圖時)。 */
  removeEmaLine(id: string): void {
    const line = this.emaLines.get(id)
    if (line) {
      this.chart.removeSeries(line)
      this.emaLines.delete(id)
    }
  }

  /** REST 歷史:整批設定。重設單調游標到歷史尾端 time(重載較舊歷史後可再串流)。 */
  setHistory(bars: BarDTO[]): void {
    this.series.setData(bars.map(toCandle))
    this.chart.timeScale().fitContent()
    this.lastBarTime = bars.length ? bars[bars.length - 1].time : null
  }

  /** WS 即時:更新最後一根或新增(LWC series.update 語意)。
   *
   * 單調守衛:丟棄嚴格較舊 time 的更新(reconnect/亂序時 LWC 會對較舊 time 拋
   * "Cannot update oldest data")。同 time 允許(重畫進行中的最後一根)。 */
  updateBar(bar: BarDTO): void {
    if (this.lastBarTime !== null && bar.time < this.lastBarTime) return
    this.series.update(toCandle(bar))
    this.lastBarTime = bar.time
  }

  /** 進出場箭頭 marker(累積);v5 用 plugin setMarkers。 */
  addMarker(spec: MarkerSpec): void {
    this.markers.push(toMarker(spec))
    this.markersApi.setMarkers([...this.markers])
  }

  setMarkers(specs: MarkerSpec[]): void {
    this.markers = specs.map(toMarker)
    this.markersApi.setMarkers([...this.markers])
  }

  /** SL/TP 水平線(以 spec.id 去重;已存在則略過)。 */
  addPriceLine(spec: PriceLineSpec): void {
    if (this.priceLines.has(spec.id)) return
    const line = this.series.createPriceLine({
      price: spec.price,
      color: spec.color,
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      axisLabelVisible: true,
      title: spec.title,
    })
    this.priceLines.set(spec.id, line)
  }

  removePriceLine(id: string): void {
    const line = this.priceLines.get(id)
    if (line) {
      this.series.removePriceLine(line)
      this.priceLines.delete(id)
    }
  }

  clearPriceLines(): void {
    for (const id of [...this.priceLines.keys()]) this.removePriceLine(id)
  }

  /**
   * 切換標的 / 週期時的命令式重置:清 candlestick 資料、所有 EMA line、
   * markers、priceLines,但**不重建 chart**(重用 chart 實例避免閃爍/洩漏)。
   * reset 後可重新 setHistory + setEmaLine。
   */
  reset(): void {
    // EMA line series 全移除。
    for (const id of [...this.emaLines.keys()]) this.removeEmaLine(id)
    // priceLines 全移除。
    this.clearPriceLines()
    // markers 清空。
    this.setMarkers([])
    // candlestick 清空(reset 後重 setHistory)。
    this.series.setData([])
    // 單調游標重設(reset 後將由 setHistory 重新建立)。
    this.lastBarTime = null
  }

  destroy(): void {
    this.chart.remove()
  }
}
