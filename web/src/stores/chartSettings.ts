/**
 * 圖表設定 store:標的 / 時間週期選擇 + EMA 疊圖開關與週期。
 *
 * 注意:此 store 只持「設定真相」(響應式,供選擇器 UI 與 watcher 觀察)。
 * chart/series 實例仍存於 CandleChart 的非響應式變數,命令式更新。
 *
 * 可選清單受限於 catalog 已灌資料(目前主要 BTCUSDT-PERP)。
 * 灌更多標的見 scripts/ingest_binance.py --symbol(文件 docs/web-chart-symbols.md)。
 */
import { defineStore } from 'pinia'

export interface SymbolOption {
  /** 完整 instrument_id,如 BTCUSDT-PERP.BINANCE。 */
  value: string
  /** UI 顯示標籤。 */
  label: string
}

export interface EmaSetting {
  enabled: boolean
  period: number
}

interface State {
  symbol: string
  timeframe: string
  symbols: SymbolOption[]
  timeframes: string[]
  emaFast: EmaSetting
  emaSlow: EmaSetting
}

/** catalog 目前已灌標的(主要 BTCUSDT-PERP;ETHUSDT-PERP 為示範占位,需 ingest 後才有資料)。 */
const DEFAULT_SYMBOLS: SymbolOption[] = [
  { value: 'BTCUSDT-PERP.BINANCE', label: 'BTCUSDT-PERP' },
  { value: 'ETHUSDT-PERP.BINANCE', label: 'ETHUSDT-PERP' },
]

export const useChartSettingsStore = defineStore('chartSettings', {
  state: (): State => ({
    symbol: 'BTCUSDT-PERP.BINANCE',
    timeframe: '1m',
    symbols: [...DEFAULT_SYMBOLS],
    timeframes: ['1m', '5m'],
    emaFast: { enabled: false, period: 12 },
    emaSlow: { enabled: false, period: 26 },
  }),
  actions: {
    setSymbol(symbol: string) {
      this.symbol = symbol
    },
    setTimeframe(timeframe: string) {
      this.timeframe = timeframe
    },
    toggleEmaFast(enabled: boolean) {
      this.emaFast.enabled = enabled
    },
    setEmaFastPeriod(period: number) {
      this.emaFast.period = period
    },
    toggleEmaSlow(enabled: boolean) {
      this.emaSlow.enabled = enabled
    },
    setEmaSlowPeriod(period: number) {
      this.emaSlow.period = period
    },
  },
})
