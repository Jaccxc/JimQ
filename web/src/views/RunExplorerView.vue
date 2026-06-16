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
import { computed, onMounted, watch } from 'vue'
import ReplayChart from '@/components/chart/ReplayChart.vue'
import { useRunExplorer, type RunExplorerApi } from '@/composables/useRunExplorer'
import type { SortKey } from '@/stores/backtestExplorer'
import type { BarDTO } from '@/types/contract'
import type { MarkerSpec, PriceLineSpec } from '@/lib/tradeMapping'
import type { EquityPoint } from '@/lib/equityCurve'

// 卡 C:單一主圖。預設顯示「選中的 run」(歷史);未選 run 時,改顯示父層傳入的
// 「剛從表單啟動、正在 scope=backtest 串流長出的 run」(liveBars/liveMarkers/
// liveEquity)。選了 run → 主圖切回該 run 的歷史資料(全量重畫)。
const props = defineProps<{
  /** api 可注入(測試決定論);預設用真實 REST client。 */
  api?: Partial<RunExplorerApi>
  /** 串流中(剛啟動)backtest 的即時 bars(未選 run 時餵主圖)。 */
  liveBars?: BarDTO[]
  liveMarkers?: MarkerSpec[]
  livePriceLines?: PriceLineSpec[]
  liveEquity?: EquityPoint[]
  /**
   * 剛完成(COMPLETED)的 run id:父層(BacktestView)在 run 完成時設此 prop →
   * 自動重載 run 列表並選取該 run → 主圖切到該 run 的歷史全量 → 從頭回放。
   */
  completedRunId?: number | null
}>()

const ex = useRunExplorer({ api: props.api })
const { store } = ex

// 主圖資料源:選了 run → run 歷史;未選 → 串流中 backtest(live*)。
const hasSelectedRun = computed(() => store.selectedRunId != null)
const chartBars = computed(() => (hasSelectedRun.value ? ex.bars.value : props.liveBars ?? []))
const chartMarkers = computed(() =>
  hasSelectedRun.value ? ex.markers.value : props.liveMarkers ?? [],
)
const chartPriceLines = computed(() =>
  hasSelectedRun.value ? ex.priceLines.value : props.livePriceLines ?? [],
)
const chartEquity = computed(() =>
  hasSelectedRun.value ? ex.equity.value : props.liveEquity ?? [],
)

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

// run 完成 → 自動重載 runs(讓剛完成的 run 進列表)+ 選取它 → 主圖回放。
watch(
  () => props.completedRunId,
  async (runId) => {
    if (runId == null) return
    await ex.loadRuns()
    await ex.selectRun(runId)
  },
)
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
      <h2 v-else>選一個 run 看 K 線與進出場(或啟動新回測即時串流)</h2>
      <!-- 改版 S4:K 線主圖內部留預設,只給外圈玻璃框(權益副圖配色見 chartController)。 -->
      <div class="chart-frame">
        <ReplayChart
          :bars="chartBars"
          :markers="chartMarkers"
          :price-lines="chartPriceLines"
          :equity="chartEquity"
          :replay="hasSelectedRun"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 改版 S4:run 列表 + run 圖各自玻璃卡(L1)。token 來自 styles/theme.css。 */
.run-explorer {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: calc(var(--spacing) * 3);
  height: 100%;
}
.run-list,
.run-chart {
  background: var(--glass-l1-bg);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-md);
  box-shadow: var(--glass-l1-shadow), var(--glass-l1-highlight);
  backdrop-filter: blur(var(--glass-l1-blur)) saturate(var(--glass-l1-saturate));
  -webkit-backdrop-filter: blur(var(--glass-l1-blur)) saturate(var(--glass-l1-saturate));
  padding: calc(var(--spacing) * 3);
}
@supports not (backdrop-filter: blur(1px)) {
  .run-list,
  .run-chart { background: var(--glass-fallback-bg); }
}
.run-list h2,
.run-chart h2 {
  margin: 0 0 calc(var(--spacing) * 2);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.01em;
}
.run-list table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.run-list th {
  text-align: right;
  padding: calc(var(--spacing) * 1.5) calc(var(--spacing) * 2);
  border-bottom: 1px solid var(--glass-l1-border);
  color: var(--color-text-muted);
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  transition: color var(--duration-fast) var(--ease-glass);
}
.run-list th:hover { color: var(--color-text); }
.run-list th:first-child,
.run-list td:first-child {
  text-align: left;
}
.run-list td {
  text-align: right;
  padding: calc(var(--spacing) * 1.5) calc(var(--spacing) * 2);
  border-bottom: 1px solid var(--surface-2);
  color: var(--color-text);
}
.run-row {
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-glass);
}
.run-row:hover {
  background: var(--surface-1);
}
.run-row.selected {
  background: var(--accent-tint-strong);
}
.empty {
  color: var(--color-text-faint);
  font-size: 13px;
}
.run-chart {
  display: flex;
  flex-direction: column;
}
/* K 線主圖外圈玻璃框:內部蠟燭/權益副圖由 chartController 控,此處只給框與圓角。 */
.chart-frame {
  flex: 1;
  min-height: 360px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--glass-l1-border);
  overflow: hidden;
  background: var(--chart-frame-bg);
}
</style>
