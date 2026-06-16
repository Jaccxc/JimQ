/**
 * 卡 #21 (W2) — backtest 結果瀏覽器 composable。
 *
 * 串接 explorer store 與 REST:
 * - loadRuns:載歷史 run 列表(供排序/比較)。
 * - selectRun:選某 run → 同時載該 run 成交(GET /backtests/{id}/trades)與其
 *   對應歷史 K 線(GET /bars,用 run 的 symbol/timeframe/start/end)→ 經
 *   tradeMapping 算出進出場 marker / SL/TP priceLine,供 chart 重畫。
 *
 * api 以參數注入(預設真實 client),測試可注入 fake 達決定論;chart/series 不進
 * 此處,marker/priceLine 規格由元件層命令式套用(復用 ChartController)。
 */
import { ref, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import {
  fetchBacktestRuns as realFetchRuns,
  fetchTrades as realFetchTrades,
  type RunSummary,
  type TradeRecord,
} from '@/api/trades'
import { fetchBars as realFetchBars, type FetchBarsParams } from '@/api/bars'
import { tradeToMarkers, tradeToPriceLines, type MarkerSpec, type PriceLineSpec } from '@/lib/tradeMapping'
import { tradesToEquityCurve, type EquityPoint } from '@/lib/equityCurve'
import { useBacktestExplorerStore } from '@/stores/backtestExplorer'
import type { BarDTO } from '@/types/contract'

const NS_PER_SEC = 1_000_000_000

/** 注入點:REST client(預設真實)。 */
export interface RunExplorerApi {
  fetchBacktestRuns: () => Promise<RunSummary[]>
  fetchTrades: (runId: number) => Promise<TradeRecord[]>
  fetchBars: (params: FetchBarsParams) => Promise<BarDTO[]>
}

export interface UseRunExplorerOptions {
  api?: Partial<RunExplorerApi>
}

/** ISO-8601 → epoch 奈秒(對齊 /bars 的 start/end 奈秒參數)。 */
function isoToNs(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000) * NS_PER_SEC
}

export function useRunExplorer(opts: UseRunExplorerOptions = {}) {
  const api: RunExplorerApi = {
    fetchBacktestRuns: opts.api?.fetchBacktestRuns ?? (() => realFetchRuns()),
    fetchTrades: opts.api?.fetchTrades ?? ((id: number) => realFetchTrades(id)),
    fetchBars: opts.api?.fetchBars ?? ((p: FetchBarsParams) => realFetchBars(p)),
  }
  const store = useBacktestExplorerStore()

  const bars: Ref<BarDTO[]> = ref([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** 目前選取 run 的進出場 marker(每筆成交 2 個)。 */
  const markers: ComputedRef<MarkerSpec[]> = computed(() =>
    store.trades.flatMap((t) => tradeToMarkers(t)),
  )
  /** 目前選取 run 的 SL/TP priceLine。 */
  const priceLines: ComputedRef<PriceLineSpec[]> = computed(() =>
    store.trades.flatMap((t) => tradeToPriceLines(t)),
  )
  /** 目前選取 run 的累積權益曲線(供主圖下方 PnL/權益副圖;換 run 自動重算)。 */
  const equity: ComputedRef<EquityPoint[]> = computed(() =>
    tradesToEquityCurve(store.trades),
  )

  async function loadRuns(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      store.setRuns(await api.fetchBacktestRuns())
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  async function selectRun(runId: number): Promise<void> {
    store.select(runId)
    const run = store.selectedRun
    if (!run) return
    loading.value = true
    error.value = null
    try {
      const [trades, runBars] = await Promise.all([
        api.fetchTrades(runId),
        api.fetchBars({
          symbol: run.instrument_id,
          timeframe: run.timeframe,
          start: isoToNs(run.start_time),
          end: isoToNs(run.end_time),
        }),
      ])
      store.setTrades(trades)
      bars.value = runBars
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  return { store, bars, markers, priceLines, equity, loading, error, loadRuns, selectRun }
}
