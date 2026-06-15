<script setup lang="ts">
/**
 * Dashboard:啟動載 REST 歷史 bars 畫初始 K 線,再開 WS 串流 replay。
 *
 * 流程:onMounted → fetchBars(#8)→ market.setHistory → useTradeSocket.connect()。
 * WS 補洞由 connection.lastSeq 驅動(dispatch 觀察 seq)。
 */
import { onMounted, onBeforeUnmount } from 'vue'
import CandleChart from '@/components/chart/CandleChart.vue'
import PositionsTable from '@/components/panels/PositionsTable.vue'
import OrdersTable from '@/components/panels/OrdersTable.vue'
import PnlWidget from '@/components/panels/PnlWidget.vue'
import ConnectionStatus from '@/components/ConnectionStatus.vue'
import { fetchBars } from '@/api/bars'
import { useMarketStore } from '@/stores/market'
import { useTradeSocket } from '@/composables/useTradeSocket'

const SYMBOL = 'BTCUSDT-PERP.BINANCE'
const TIMEFRAME = '1m'
const CHANNELS = ['bars', 'orders', 'fills', 'positions', 'pnl']

const market = useMarketStore()
const socket = useTradeSocket({ channels: CHANNELS })

onMounted(async () => {
  try {
    const bars = await fetchBars({ symbol: SYMBOL, timeframe: TIMEFRAME })
    market.setHistory(bars)
  } catch (err) {
    // 歷史載入失敗不擋串流;記錄即可。
    console.warn('歷史 bars 載入失敗', err)
  }
  socket.connect()
})

onBeforeUnmount(() => socket.disconnect())
</script>

<template>
  <div class="dashboard">
    <header class="topbar">
      <h1>JimQ — {{ SYMBOL }} {{ TIMEFRAME }}</h1>
      <ConnectionStatus />
    </header>
    <main class="grid">
      <section class="chart-cell">
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
.dashboard { display: flex; flex-direction: column; height: 100vh; background: #0e1117; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; border-bottom: 1px solid #1c2230;
}
.topbar h1 { font-size: 14px; color: #d1d4dc; margin: 0; font-weight: 600; }
.grid { flex: 1; display: grid; grid-template-columns: 1fr 320px; min-height: 0; }
.chart-cell { min-height: 0; padding: 8px; }
.side { border-left: 1px solid #1c2230; overflow-y: auto; }
</style>
