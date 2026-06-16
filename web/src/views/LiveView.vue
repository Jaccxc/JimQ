<script setup lang="ts">
/**
 * 卡 #27 (P2-S1) — Live 頁(/live)。
 *
 * 即時 K 線:複用 CandleChart/ChartController + useTradeSocket 顯示來自 Redis
 * 串流的真即時 BTCUSDT-PERP(live 資料節點 → Redis Streams → consumer → WS)。
 * 含 symbol/timeframe 選擇器 + EMA(W3)。
 *
 * 卡 #28 (P2-S2):訂單/成交/部位/PnL 面板接**真 live** 值 —— testnet 交易節點
 * (scripts/run_live_trade.py)下 paper 單 → 事件經 Redis→consumer→WS→stores
 * (dispatch.ts 路由)→ PnlWidget / PositionsTable / OrdersTable(成交)即時顯示。
 * 移除 P2-S2 佔位文字(本頁不再 read-only)。
 *
 * 掛載時 appMode.setLive() → header mode badge 顯示 LIVE-TESTNET。
 * 流程同 Dashboard:onMounted → 載 REST 歷史 bars → 開 WS 串流。
 */
import { onMounted, onBeforeUnmount } from 'vue'
import CandleChart from '@/components/chart/CandleChart.vue'
import ChartControls from '@/components/controls/ChartControls.vue'
import StrategyControls from '@/components/controls/StrategyControls.vue'
import PositionsTable from '@/components/panels/PositionsTable.vue'
import OrdersTable from '@/components/panels/OrdersTable.vue'
import PnlWidget from '@/components/panels/PnlWidget.vue'
import { useChartSettingsStore } from '@/stores/chartSettings'
import { useAppModeStore } from '@/stores/appMode'
import { useTradeSocket } from '@/composables/useTradeSocket'
import { useChartData } from '@/composables/useChartData'
import { fetchLiveBars } from '@/api/bars'
import type { FetchBarsParams } from '@/api/bars'

const CHANNELS = ['bars', 'orders', 'fills', 'positions', 'pnl']
/** Live 頁初始載入根數(近期真 klines;與 live WS 串流接續)。 */
const LIVE_BARS_LIMIT = 1000

const settings = useChartSettingsStore()
const appMode = useAppModeStore()
const socket = useTradeSocket({ channels: CHANNELS })
// Live 頁初始載入用近期真 klines(/api/v1/live/bars,同 live testnet venue ~66k),
// 取代 2024 回測 catalog(/api/v1/bars)消除價位斷裂。switchTo/reload 走同一路徑。
const chartData = useChartData({
  socket,
  fetchBars: (p: FetchBarsParams) =>
    fetchLiveBars({ symbol: p.symbol, timeframe: p.timeframe, limit: LIVE_BARS_LIMIT }),
})

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
    <StrategyControls />
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
</style>
