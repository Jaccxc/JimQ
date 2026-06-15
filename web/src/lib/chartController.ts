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
  createSeriesMarkers,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type IPriceLine,
  type CandlestickData,
  type SeriesMarker,
  type UTCTimestamp,
  type Time,
} from 'lightweight-charts'
import type { BarDTO } from '@/types/contract'
import type { MarkerSpec, PriceLineSpec } from '@/lib/tradeMapping'

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

  constructor(container: HTMLElement) {
    this.chart = createChart(container, {
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
    this.series = this.chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    })
    this.markersApi = createSeriesMarkers(this.series, [])
  }

  /** REST 歷史:整批設定。 */
  setHistory(bars: BarDTO[]): void {
    this.series.setData(bars.map(toCandle))
    this.chart.timeScale().fitContent()
  }

  /** WS 即時:更新最後一根或新增(LWC series.update 語意)。 */
  updateBar(bar: BarDTO): void {
    this.series.update(toCandle(bar))
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

  destroy(): void {
    this.chart.remove()
  }
}
