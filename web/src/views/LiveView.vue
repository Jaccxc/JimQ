<script setup lang="ts">
/**
 * 卡 #27 (P2-S1) — Live 頁(/live)。
 *
 * 即時 K 線:複用 CandleChart/ChartController + useTradeSocket 顯示來自 Redis
 * 串流的真即時 BTCUSDT-PERP(live 資料節點 → Redis Streams → consumer → WS)。
 * 含 symbol/timeframe 選擇器 + EMA(W3)。部位/PnL 面板先佔位(下單在 P2-S2)。
 *
 * 掛載時 appMode.setLive() → header mode badge 顯示 LIVE-TESTNET。
 * 流程同 Dashboard:onMounted → 載 REST 歷史 bars → 開 WS 串流。
 */
import { onMounted, onBeforeUnmount } from 'vue'
import CandleChart from '@/components/chart/CandleChart.vue'
import ChartControls from '@/components/controls/ChartControls.vue'
import PositionsTable from '@/components/panels/PositionsTable.vue'
import PnlWidget from '@/components/panels/PnlWidget.vue'
import { useChartSettingsStore } from '@/stores/chartSettings'
import { useAppModeStore } from '@/stores/appMode'
import { useTradeSocket } from '@/composables/useTradeSocket'
import { useChartData } from '@/composables/useChartData'

const CHANNELS = ['bars', 'orders', 'fills', 'positions', 'pnl']

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

onMounted(async () => {
  // 資料來源 = live 節點 → header badge 顯示 LIVE-TESTNET。
  appMode.setLive()
  try {
    await chartData.reload()
  } catch (err) {
    console.warn('歷史 bars 載入失敗', err)
  }
  socket.connect()
})

onBeforeUnmount(() => {
  socket.disconnect()
})
</script>

<template>
  <div class="live">
    <header class="topbar">
      <h1>Live — {{ settings.symbol }} {{ settings.timeframe }}</h1>
    </header>
    <main class="grid">
      <section class="chart-cell">
        <ChartControls @switch="onSwitch" />
        <CandleChart />
      </section>
      <aside class="side">
        <PnlWidget />
        <PositionsTable />
        <p class="placeholder">下單 / 部位變動將於 P2-S2 接入(本頁 read-only live 資料)。</p>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.live { display: flex; flex-direction: column; height: 100%; background: #0e1117; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; border-bottom: 1px solid #1c2230;
}
.topbar h1 { font-size: 14px; color: #d1d4dc; margin: 0; font-weight: 600; }
.grid { flex: 1; display: grid; grid-template-columns: 1fr 320px; min-height: 0; }
.chart-cell { min-height: 0; padding: 8px; display: flex; flex-direction: column; }
.chart-cell > :last-child { flex: 1; min-height: 0; }
.side { border-left: 1px solid #1c2230; overflow-y: auto; padding-bottom: 12px; }
.placeholder { font-size: 11px; color: #6b7280; padding: 10px 12px; line-height: 1.5; }
</style>
