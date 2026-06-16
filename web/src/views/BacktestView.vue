<script setup lang="ts">
/**
 * 卡 C — Backtest 頁(/backtest):單一主圖 + PnL/權益副圖。
 *
 * 版面:頂部 BacktestLauncher(觸發 + 輪詢狀態)→ 單一主圖(RunExplorer 的
 * ReplayChart):
 *  - 預設顯示「選中的 run」(從 History 列表選過去 run → 重載該 run K 線 +
 *    進出場箭頭 + SL/TP + 權益副圖)。
 *  - 未選 run 時,顯示「剛從表單啟動、正在 scope=backtest 串流長出的 run」——
 *    串流 bars 經 market store 餵進同一主圖即時長出(用卡 A scope=backtest,
 *    與 Live 分頁互不污染)。
 *
 * 移除了舊版會混入 live 的中間 CandleChart(擺反且亂)。掛載時
 * appMode.setBacktest() → badge = BACKTEST。
 */
import { computed, onMounted, onBeforeUnmount } from 'vue'
import BacktestLauncher from '@/components/controls/BacktestLauncher.vue'
import RunExplorerView from '@/views/RunExplorerView.vue'
import { fetchBacktestRun } from '@/api/backtests'
import { useBacktestRunStore, type RunStatus } from '@/stores/backtestRun'
import { useAppModeStore } from '@/stores/appMode'
import { useMarketStore } from '@/stores/market'
import { useFillsStore } from '@/stores/fills'
import { useTradeSocket } from '@/composables/useTradeSocket'
import { useChartData } from '@/composables/useChartData'
import { fillToMarker } from '@/lib/tradeMapping'
import type { FetchBarsParams } from '@/api/bars'
import type { BarDTO } from '@/types/contract'
import type { RunExplorerApi } from '@/composables/useRunExplorer'

const CHANNELS = ['bars', 'orders', 'fills', 'positions', 'pnl']

// 注入點(測試決定論);預設用真實 client/fetch。
const props = defineProps<{
  explorerApi?: Partial<RunExplorerApi>
  fetchBars?: (params: FetchBarsParams) => Promise<BarDTO[]>
}>()

const runStore = useBacktestRunStore()
const appMode = useAppModeStore()
const market = useMarketStore()
const fills = useFillsStore()
// 卡 A:Backtest 即時串流訂 scope=backtest → 與 Live 分頁互不污染。
const socket = useTradeSocket({ channels: CHANNELS, scope: 'backtest' })
const chartData = useChartData({ socket, fetchBars: props.fetchBars })

// 未選 run 時主圖顯示串流中的 backtest:market store 的 bars + fills marker。
const liveBars = computed<BarDTO[]>(() => market.bars)
const liveMarkers = computed(() => fills.fills.map((f) => fillToMarker(f)))

let pollTimer: ReturnType<typeof setInterval> | null = null

function onLaunched(runId: number) {
  // 新回測:清掉上一輪殘留,讓新 run 從頭串進主圖長出。
  market.setHistory([])
  socket.connect()
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const run = await fetchBacktestRun(runId)
      runStore.setStatus(run.status as RunStatus)
      if (run.status === 'COMPLETED' || run.status === 'FAILED') {
        if (pollTimer) clearInterval(pollTimer)
        pollTimer = null
      }
    } catch (err) {
      console.warn('輪詢 run 狀態失敗', err)
    }
  }, 1000)
}

onMounted(async () => {
  appMode.setBacktest()
  socket.connect()
})

onBeforeUnmount(() => {
  socket.disconnect()
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="backtest">
    <header class="topbar">
      <h1>Backtest</h1>
    </header>
    <BacktestLauncher @launched="onLaunched" />
    <section class="explorer-cell">
      <RunExplorerView
        :api="props.explorerApi"
        :live-bars="liveBars"
        :live-markers="liveMarkers"
      />
    </section>
  </div>
</template>

<style scoped>
/* 改版 S4:Backtest 頁殼。大面積背景禁用 backdrop-filter(只給卡片/header),
 * 故頁底用實心 bg token;launcher/explorer 各自玻璃化。 */
.backtest {
  display: flex; flex-direction: column;
  height: 100%; overflow-y: auto;
  background: var(--color-bg);
  padding: calc(var(--spacing) * 3);
  gap: calc(var(--spacing) * 3);
}
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: calc(var(--spacing) * 2) calc(var(--spacing) * 2);
}
.topbar h1 {
  font-size: 16px; color: var(--color-text); margin: 0;
  font-weight: 600; letter-spacing: -0.01em;
}
.explorer-cell { flex: 1; min-height: 480px; }
</style>
