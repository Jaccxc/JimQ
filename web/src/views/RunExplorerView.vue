<script setup lang="ts">
/**
 * 卡 #21 (W2) — Backtest 結果瀏覽器視圖。
 *
 * 左:歷史 run 列表表格(依指標排序/比較,點欄頭切換排序);點任一列 → 選取該
 * run。右:選取 run 的重播 K 線(整段 bars + 該次進出場 marker / SL/TP)。
 *
 * 邏輯全在 useRunExplorer composable + backtestExplorer store(已 Vitest 覆蓋);
 * 本視圖僅綁定與命令式重畫(復用 ChartController/tradeMapping)。
 */
import { onMounted } from 'vue'
import ReplayChart from '@/components/chart/ReplayChart.vue'
import { useRunExplorer, type RunExplorerApi } from '@/composables/useRunExplorer'
import type { SortKey } from '@/stores/backtestExplorer'

// api 可注入(測試決定論);預設用真實 REST client。
const props = defineProps<{ api?: Partial<RunExplorerApi> }>()

const ex = useRunExplorer({ api: props.api })
const { store } = ex

const METRIC_COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'id', label: 'Run' },
  { key: 'total_return', label: 'Return' },
  { key: 'sharpe', label: 'Sharpe' },
  { key: 'max_drawdown', label: 'MaxDD' },
  { key: 'num_trades', label: 'Trades' },
  { key: 'final_balance', label: 'Balance' },
]

function onSort(key: SortKey) {
  // 同欄再點切換方向;換欄預設降冪。
  const dir = store.sortKey === key && store.sortDir === 'desc' ? 'asc' : 'desc'
  store.sortBy(key, dir)
}

function fmt(v: string | number | null | undefined): string {
  if (v == null) return '—'
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isNaN(n) ? String(v) : n.toFixed(4)
}

onMounted(() => {
  ex.loadRuns()
})
</script>

<template>
  <section class="run-explorer" data-testid="run-explorer">
    <div class="run-list">
      <h2>Backtest Runs</h2>
      <table>
        <thead>
          <tr>
            <th
              v-for="col in METRIC_COLUMNS"
              :key="col.key"
              class="sortable"
              :data-testid="`sort-${col.key}`"
              @click="onSort(col.key)"
            >
              {{ col.label }}
              <span v-if="store.sortKey === col.key">{{ store.sortDir === 'desc' ? '▼' : '▲' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="run in store.sortedRuns"
            :key="run.id"
            class="run-row"
            :class="{ selected: run.id === store.selectedRunId }"
            :data-testid="`run-row-${run.id}`"
            @click="ex.selectRun(run.id)"
          >
            <td>#{{ run.id }}</td>
            <td>{{ fmt(run.total_return) }}</td>
            <td>{{ fmt(run.sharpe) }}</td>
            <td>{{ fmt(run.max_drawdown) }}</td>
            <td>{{ run.num_trades ?? '—' }}</td>
            <td>{{ fmt(run.final_balance) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="store.runs.length === 0" class="empty">尚無 run。先從 Dashboard 跑一次 backtest。</p>
    </div>

    <div class="run-chart">
      <h2 v-if="store.selectedRun">
        Run #{{ store.selectedRun.id }} · {{ store.selectedRun.strategy_name }} ·
        {{ store.selectedRun.instrument_id }} {{ store.selectedRun.timeframe }}
      </h2>
      <h2 v-else>選一個 run 看 K 線與進出場</h2>
      <ReplayChart
        :bars="ex.bars.value"
        :markers="ex.markers.value"
        :price-lines="ex.priceLines.value"
        :equity="ex.equity.value"
      />
    </div>
  </section>
</template>

<style scoped>
.run-explorer {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 12px;
  height: 100%;
  padding: 12px;
}
.run-list table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.run-list th {
  text-align: right;
  padding: 6px 8px;
  border-bottom: 1px solid #2a3142;
  cursor: pointer;
  user-select: none;
}
.run-list th:first-child,
.run-list td:first-child {
  text-align: left;
}
.run-list td {
  text-align: right;
  padding: 6px 8px;
  border-bottom: 1px solid #1c2230;
}
.run-row {
  cursor: pointer;
}
.run-row:hover {
  background: #161b26;
}
.run-row.selected {
  background: #1f2937;
}
.empty {
  color: #8a93a6;
  font-size: 13px;
}
.run-chart {
  display: flex;
  flex-direction: column;
}
</style>
