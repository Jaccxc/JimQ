<script setup lang="ts">
/**
 * 卡 #27 (P2-S1) — Backtest 頁(/backtest)。
 *
 * 整併既有 W1/W2:BacktestLauncher(觸發 + 輪詢狀態 + 串流圖)+ RunExplorer
 * (歷史 run 列表 + 重播圖)。掛載時 appMode.setBacktest() → badge = BACKTEST。
 */
import { onMounted, onBeforeUnmount } from 'vue'
import CandleChart from '@/components/chart/CandleChart.vue'
import ChartControls from '@/components/controls/ChartControls.vue'
import OrdersTable from '@/components/panels/OrdersTable.vue'
import PositionsTable from '@/components/panels/PositionsTable.vue'
import PnlWidget from '@/components/panels/PnlWidget.vue'
import BacktestLauncher from '@/components/controls/BacktestLauncher.vue'
import RunExplorerView from '@/views/RunExplorerView.vue'
import { fetchBacktestRun } from '@/api/backtests'
import { useBacktestRunStore, type RunStatus } from '@/stores/backtestRun'
import { useChartSettingsStore } from '@/stores/chartSettings'
import { useAppModeStore } from '@/stores/appMode'
import { useTradeSocket } from '@/composables/useTradeSocket'
import { useChartData } from '@/composables/useChartData'

const CHANNELS = ['bars', 'orders', 'fills', 'positions', 'pnl']

const runStore = useBacktestRunStore()
const settings = useChartSettingsStore()
const appMode = useAppModeStore()
const socket = useTradeSocket({ channels: CHANNELS })
const chartData = useChartData({ socket })

async function onSwitch(sel: { symbol: string; timeframe: string }) {
  try {
    await chartData.switchTo(sel)
  } catch (err) {
    console.warn('切換標的/週期失敗', err)
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

function onLaunched(runId: number) {
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
  try {
    await chartData.reload()
  } catch (err) {
    console.warn('歷史 bars 載入失敗', err)
  }
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
      <h1>Backtest — {{ settings.symbol }} {{ settings.timeframe }}</h1>
    </header>
    <BacktestLauncher @launched="onLaunched" />
    <main class="grid">
      <section class="chart-cell">
        <ChartControls @switch="onSwitch" />
        <CandleChart />
      </section>
      <aside class="side">
        <PnlWidget />
        <PositionsTable />
        <OrdersTable />
      </aside>
    </main>
    <section class="explorer-cell">
      <RunExplorerView />
    </section>
  </div>
</template>

<style scoped>
.backtest { display: flex; flex-direction: column; height: 100%; overflow-y: auto; background: #0e1117; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; border-bottom: 1px solid #1c2230;
}
.topbar h1 { font-size: 14px; color: #d1d4dc; margin: 0; font-weight: 600; }
.grid { display: grid; grid-template-columns: 1fr 320px; min-height: 360px; }
.chart-cell { min-height: 0; padding: 8px; display: flex; flex-direction: column; }
.chart-cell > :last-child { flex: 1; min-height: 320px; }
.side { border-left: 1px solid #1c2230; overflow-y: auto; }
.explorer-cell { border-top: 1px solid #1c2230; min-height: 360px; }
</style>
