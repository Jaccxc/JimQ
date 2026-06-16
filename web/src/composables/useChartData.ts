/**
 * useChartData — 標的 / 時間週期切換的歷史重載 + 串流重訂協調器。
 *
 * 職責(對齊卡 #22):
 * - reload():用目前 chartSettings 的 symbol/timeframe 取 REST 歷史 bars
 *   → market.setHistory(整批替換,清掉舊標的殘留)。
 * - switchTo({symbol, timeframe}):更新設定 → 清空舊 bars → reload → 重訂串流
 *   (socket.disconnect → connect)。同值為 no-op 避免抖動。
 *
 * 依賴注入(fetchBars / socket)以利單元測試決定論;預設用真實 api/composable。
 * 不持有 chart/series 實例(那些在 CandleChart 非響應式變數)。
 */
import { fetchBars as defaultFetchBars, type FetchBarsParams } from '@/api/bars'
import { useChartSettingsStore } from '@/stores/chartSettings'
import { useMarketStore } from '@/stores/market'
import type { BarDTO } from '@/types/contract'

export interface ChartSocket {
  connect: () => void
  disconnect: () => void
}

export interface UseChartDataOptions {
  /** 注入 bars REST client(測試用)。 */
  fetchBars?: (params: FetchBarsParams) => Promise<BarDTO[]>
  /** 串流連線(重訂時 disconnect→connect)。 */
  socket: ChartSocket
  /**
   * market store scope 命名空間(真 bug 修復):Live 頁='live'(預設)、
   * Backtest 頁='backtest' → 歷史/串流 bars 寫進對應命名空間,不污染另一邊。
   */
  scope?: string
}

export interface ChartData {
  reload: () => Promise<void>
  switchTo: (sel: { symbol: string; timeframe: string }) => Promise<void>
}

export function useChartData(opts: UseChartDataOptions): ChartData {
  const fetchBars = opts.fetchBars ?? defaultFetchBars
  const socket = opts.socket
  const scope = opts.scope ?? 'live'

  async function reload(): Promise<void> {
    const settings = useChartSettingsStore()
    const market = useMarketStore(scope)
    const bars = await fetchBars({
      symbol: settings.symbol,
      timeframe: settings.timeframe,
    })
    // 整批替換:setHistory 內部去重保序,確保不殘留舊標的 bars。
    market.setHistory(bars)
  }

  async function switchTo(sel: { symbol: string; timeframe: string }): Promise<void> {
    const settings = useChartSettingsStore()
    if (sel.symbol === settings.symbol && sel.timeframe === settings.timeframe) {
      return // 同值 no-op。
    }
    settings.setSymbol(sel.symbol)
    settings.setTimeframe(sel.timeframe)
    // 清空舊標的資料,避免短暫殘留/混圖。
    useMarketStore(scope).setHistory([])
    await reload()
    // 重訂對應串流(目前 channel 不分標的;重連讓 gateway 重發快照)。
    socket.disconnect()
    socket.connect()
  }

  return { reload, switchTo }
}
