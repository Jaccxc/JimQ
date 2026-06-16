/**
 * 行為測試:chartSettings store + useChartData composable。
 *
 * chartSettings:持 symbol / timeframe 選擇與可選清單、EMA 開關與週期。
 * useChartData:切 symbol/timeframe 時 → fetchBars 重載歷史 → market.setHistory
 *   → 重訂串流(socket reconnect)。注入 fetchBars/socket 以決定論測試。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChartSettingsStore } from '@/stores/chartSettings'
import { useChartData } from '@/composables/useChartData'
import { useMarketStore } from '@/stores/market'
import type { BarDTO } from '@/types/contract'

beforeEach(() => setActivePinia(createPinia()))

const NS = 1_000_000_000
function bar(time: number, close: number): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(close),
    high: String(close),
    low: String(close),
    close: String(close),
    volume: '1',
  }
}

describe('chartSettings store', () => {
  it('有預設 symbol/timeframe 與可選清單', () => {
    const s = useChartSettingsStore()
    expect(s.symbol).toBeTruthy()
    expect(s.timeframe).toBeTruthy()
    expect(s.symbols.length).toBeGreaterThan(0)
    expect(s.timeframes.length).toBeGreaterThan(0)
  })

  it('setSymbol / setTimeframe 更新選擇', () => {
    const s = useChartSettingsStore()
    s.setSymbol('ETHUSDT-PERP.BINANCE')
    expect(s.symbol).toBe('ETHUSDT-PERP.BINANCE')
    s.setTimeframe('5m')
    expect(s.timeframe).toBe('5m')
  })

  it('EMA 開關與週期可調', () => {
    const s = useChartSettingsStore()
    expect(s.emaFast.enabled).toBe(false)
    s.toggleEmaFast(true)
    s.setEmaFastPeriod(12)
    expect(s.emaFast.enabled).toBe(true)
    expect(s.emaFast.period).toBe(12)
    s.toggleEmaSlow(true)
    s.setEmaSlowPeriod(26)
    expect(s.emaSlow.enabled).toBe(true)
    expect(s.emaSlow.period).toBe(26)
  })
})

describe('useChartData 切換重載', () => {
  it('reload 用目前 symbol/timeframe 取 bars 並 setHistory', async () => {
    const settings = useChartSettingsStore()
    settings.setSymbol('BTCUSDT-PERP.BINANCE')
    settings.setTimeframe('1m')
    const fetchBars = vi.fn(async () => [bar(100, 1), bar(160, 2)])
    const socket = { connect: vi.fn(), disconnect: vi.fn() }
    const cd = useChartData({ fetchBars, socket })
    await cd.reload()
    expect(fetchBars).toHaveBeenCalledWith(
      expect.objectContaining({ symbol: 'BTCUSDT-PERP.BINANCE', timeframe: '1m' }),
    )
    expect(useMarketStore().bars).toHaveLength(2)
  })

  it('switchTo 改 symbol → 清空舊 bars、重載、重訂串流', async () => {
    const market = useMarketStore()
    market.setHistory([bar(100, 1)])
    const fetchBars = vi.fn(async () => [bar(200, 5), bar(260, 6), bar(320, 7)])
    const socket = { connect: vi.fn(), disconnect: vi.fn() }
    const cd = useChartData({ fetchBars, socket })
    await cd.switchTo({ symbol: 'ETHUSDT-PERP.BINANCE', timeframe: '5m' })

    const settings = useChartSettingsStore()
    expect(settings.symbol).toBe('ETHUSDT-PERP.BINANCE')
    expect(settings.timeframe).toBe('5m')
    // 舊 bars 被新的取代(非殘留 + 累加)。
    expect(market.bars).toHaveLength(3)
    expect(market.bars[0].time).toBe(200)
    // 重訂串流:先斷再連。
    expect(socket.disconnect).toHaveBeenCalled()
    expect(socket.connect).toHaveBeenCalled()
  })

  it('switchTo 同值不重複重載(no-op 避免抖動)', async () => {
    const settings = useChartSettingsStore()
    settings.setSymbol('BTCUSDT-PERP.BINANCE')
    settings.setTimeframe('1m')
    const fetchBars = vi.fn(async () => [bar(100, 1)])
    const socket = { connect: vi.fn(), disconnect: vi.fn() }
    const cd = useChartData({ fetchBars, socket })
    await cd.switchTo({ symbol: 'BTCUSDT-PERP.BINANCE', timeframe: '1m' })
    expect(fetchBars).not.toHaveBeenCalled()
    expect(socket.disconnect).not.toHaveBeenCalled()
  })
})
