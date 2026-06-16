<script setup lang="ts">
/**
 * 卡 #23 (W4) — Research 頁(/research)研究儀表板。
 * 改版 S5:全頁玻璃化(GlassPanel + token CSS),保留所有資料抓取/觸發行為。
 *
 * 三塊:
 *  1. Models:已登記模型列表(GET /api/v1/models)— name/version/framework/
 *     metrics/created_at 表格。每列可 Deploy → 跳 Backtest 頁(回測該模型)。
 *  2. MLflow runs:某 experiment 的 runs(經 api MLflow proxy)— params/metrics
 *     比較表;可切換 experiment。
 *  3. 觸發 job:從 web 觸發 dataset build / 訓練 job(POST /api/v1/research/jobs)
 *     → 顯示回傳的 job 狀態(MVP:job 被觸發並可看狀態)。
 *
 * 資料/觸發走 useResearch composable(api 可由 prop 注入,測試決定論)。掛載時
 * appMode.setBacktest()(研究操作歷史/registry 資料,非 live testnet)。
 */
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useResearch, type ResearchApi } from '@/composables/useResearch'
import { useAppModeStore } from '@/stores/appMode'
import { GlassPanel } from '@/components/ui/glass'
import type { ModelRecord } from '@/api/research'

const props = defineProps<{ api?: Partial<ResearchApi> }>()

const appMode = useAppModeStore()
const research = useResearch({ api: props.api })
const store = research.store

// 測試只掛 pinia(無 router);useRouter 在無 router 時回 undefined,需守。
const router = useRouter()

/** MLflow runs 表的指標欄(取 runs 出現過的 metric key 聯集,穩定排序)。 */
const metricKeys = computed(() => {
  const keys = new Set<string>()
  for (const run of store.runs) {
    for (const k of Object.keys(run.metrics)) keys.add(k)
  }
  return [...keys].sort()
})

function fmt(v: number | undefined): string {
  return v == null ? '—' : String(v)
}

function onSelectExperiment(e: Event) {
  const id = (e.target as HTMLSelectElement).value
  void research.selectExperiment(id)
}

/** Deploy 模型 → 跳 Backtest 頁回測(帶模型識別供後續預填)。 */
function onDeploy(m: ModelRecord) {
  void router?.push({ path: '/backtest', query: { model: String(m.id), version: m.version } })
}

onMounted(async () => {
  appMode.setBacktest()
  await Promise.all([research.loadModels(), research.loadExperiments()])
})
</script>

<template>
  <div class="research" data-testid="research-dashboard">
    <header class="topbar">
      <h1>Research</h1>
      <span class="subtitle">Model registry · MLflow runs · job orchestration</span>
    </header>

    <main class="grid">
      <!-- 1) 已登記模型 -->
      <GlassPanel as="section" class="panel panel-models" :padded="false">
        <div class="panel-head">
          <h2>Models</h2>
          <span class="count" data-testid="models-count">{{ store.models.length }}</span>
        </div>
        <div class="tbl-scroll">
          <table class="tbl" data-testid="models-table">
            <thead>
              <tr>
                <th>name</th><th>version</th><th>framework</th>
                <th class="num">sharpe</th><th>created_at</th><th class="act-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in store.models" :key="m.id" class="data-row">
                <td class="strong">{{ m.name }}</td>
                <td><span class="ver-pill">{{ m.version }}</span></td>
                <td class="muted">{{ m.framework }}</td>
                <td class="num tabular-nums">{{ m.sharpe ?? '—' }}</td>
                <td class="muted tabular-nums">{{ m.created_at }}</td>
                <td class="act-col">
                  <button
                    type="button"
                    class="deploy-btn"
                    :data-testid="`deploy-model-${m.id}`"
                    @click="onDeploy(m)"
                  >
                    Deploy → backtest
                  </button>
                </td>
              </tr>
              <tr v-if="store.models.length === 0" class="empty">
                <td colspan="6">尚無已登記模型</td>
              </tr>
            </tbody>
          </table>
        </div>
      </GlassPanel>

      <!-- 2) MLflow runs 比較 -->
      <GlassPanel as="section" class="panel" :padded="false">
        <div class="panel-head">
          <h2>MLflow runs</h2>
          <div class="select-wrap" v-if="store.experiments.length">
            <select
              class="exp-select"
              data-testid="experiment-select"
              :value="store.selectedExperimentId ?? ''"
              @change="onSelectExperiment"
            >
              <option v-for="e in store.experiments" :key="e.experiment_id" :value="e.experiment_id">
                {{ e.name }}
              </option>
            </select>
          </div>
        </div>
        <div class="tbl-scroll">
          <table class="tbl" data-testid="mlflow-runs-table">
            <thead>
              <tr>
                <th>run</th><th>status</th>
                <th v-for="k in metricKeys" :key="k" class="num">{{ k }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in store.runs" :key="r.run_id" class="data-row">
                <td class="strong">{{ r.run_name ?? r.run_id }}</td>
                <td><span class="status-pill" :data-status="r.status">{{ r.status }}</span></td>
                <td v-for="k in metricKeys" :key="k" class="num tabular-nums">{{ fmt(r.metrics[k]) }}</td>
              </tr>
              <tr v-if="store.runs.length === 0" class="empty">
                <td :colspan="2 + metricKeys.length">尚無 runs(連 MLflow 服務後顯示)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </GlassPanel>

      <!-- 3) 觸發 job -->
      <GlassPanel as="section" class="panel panel-job" :padded="false">
        <div class="panel-head">
          <h2>觸發 job</h2>
        </div>
        <div class="job-body">
        <p class="job-lead">手動觸發資料建置或模型訓練 job,在下方追蹤狀態。</p>
        <div class="actions">
          <button
            type="button"
            class="job-btn primary"
            data-testid="trigger-build-dataset"
            :disabled="research.jobPending.value"
            @click="research.runJob('BUILD_DATASET', {})"
          >
            Build dataset
          </button>
          <button
            type="button"
            class="job-btn"
            data-testid="trigger-train"
            :disabled="research.jobPending.value"
            @click="research.runJob('TRAIN', {})"
          >
            Train model
          </button>
        </div>
        <p v-if="store.lastJob" class="job-status" data-testid="last-job-status">
          <span class="dot" :data-status="store.lastJob.status" />
          job #{{ store.lastJob.job_id }} — {{ store.lastJob.status }}
        </p>
        <p v-else class="job-hint">觸發後在此顯示 job id 與狀態。</p>
        </div>
      </GlassPanel>
    </main>
  </div>
</template>

<style scoped>
/* 改版 S5:Research 頁玻璃化。大面積背景禁 backdrop-filter(只給卡片);
 * 頁底用實心 bg token;各區塊用 GlassPanel(L1)。token 來自 styles/theme.css。 */
.research {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  background: var(--color-bg);
  padding: calc(var(--spacing) * 3);
  gap: calc(var(--spacing) * 3);
}
.topbar {
  display: flex;
  align-items: baseline;
  gap: calc(var(--spacing) * 3);
  padding: calc(var(--spacing) * 2) calc(var(--spacing) * 2);
}
.topbar h1 {
  font-size: 16px;
  color: var(--color-text);
  margin: 0;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.subtitle {
  font-size: 12px;
  color: var(--color-text-faint);
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: calc(var(--spacing) * 3);
}
.panel {
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
}
.panel-models {
  grid-column: 1 / -1;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: calc(var(--spacing) * 2);
  padding: calc(var(--spacing) * 3) calc(var(--spacing) * 4) calc(var(--spacing) * 2);
}
.panel h2 {
  font-size: 13px;
  color: var(--color-text);
  margin: 0;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.count {
  font-size: 11px;
  color: var(--color-text-muted);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-xs);
  padding: 1px 7px;
  font-variant-numeric: tabular-nums;
}

/* ---- 表格 ---- */
.tbl-scroll {
  overflow-x: auto;
  padding: 0 calc(var(--spacing) * 1) calc(var(--spacing) * 2);
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  color: var(--color-text);
}
.tbl th {
  text-align: left;
  color: var(--color-text-muted);
  font-weight: 500;
  padding: calc(var(--spacing) * 1.5) calc(var(--spacing) * 2.5);
  border-bottom: 1px solid var(--glass-l1-border);
  white-space: nowrap;
}
.tbl th.num,
.tbl td.num {
  text-align: right;
}
.tbl th.act-col,
.tbl td.act-col {
  text-align: right;
  width: 1%;
  white-space: nowrap;
}
.tbl td {
  padding: calc(var(--spacing) * 1.75) calc(var(--spacing) * 2.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.tbl tbody tr.data-row {
  transition: background var(--duration-fast) var(--ease-glass);
}
.tbl tbody tr.data-row:hover {
  background: rgba(255, 255, 255, 0.04);
}
.tbl td.strong {
  color: var(--color-text);
  font-weight: 500;
}
.tbl td.muted {
  color: var(--color-text-muted);
}
.tbl tr.empty td {
  color: var(--color-text-faint);
  text-align: center;
  padding: calc(var(--spacing) * 5);
  border-bottom: none;
}

.ver-pill {
  font-size: 11px;
  color: var(--color-accent);
  background: rgba(10, 132, 255, 0.12);
  border: 1px solid rgba(10, 132, 255, 0.25);
  border-radius: var(--radius-xs);
  padding: 1px 6px;
  font-variant-numeric: tabular-nums;
}

.status-pill {
  font-size: 11px;
  color: var(--color-text-muted);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-xs);
  padding: 1px 7px;
}
.status-pill[data-status='FINISHED'] {
  color: var(--color-up);
  border-color: rgba(38, 208, 124, 0.3);
}
.status-pill[data-status='FAILED'] {
  color: var(--color-down);
  border-color: rgba(255, 92, 92, 0.3);
}
.status-pill[data-status='RUNNING'] {
  color: var(--color-accent);
  border-color: rgba(10, 132, 255, 0.3);
}

/* ---- experiment select ---- */
.select-wrap {
  position: relative;
}
.exp-select {
  appearance: none;
  background: rgba(11, 14, 20, 0.5);
  color: var(--color-text);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-xs);
  font-size: 12px;
  padding: 4px 24px 4px 8px;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-glass),
    box-shadow var(--duration-fast) var(--ease-glass);
}
.exp-select:hover {
  border-color: rgba(255, 255, 255, 0.2);
}
.exp-select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 1px var(--color-accent);
}
.select-wrap::after {
  content: '';
  position: absolute;
  right: 9px;
  top: 50%;
  width: 6px;
  height: 6px;
  border-right: 1.5px solid var(--color-text-muted);
  border-bottom: 1.5px solid var(--color-text-muted);
  transform: translateY(-70%) rotate(45deg);
  pointer-events: none;
}

/* ---- deploy 按鈕 ---- */
.deploy-btn {
  font-size: 11px;
  font-weight: 500;
  padding: calc(var(--spacing) * 1) calc(var(--spacing) * 2.5);
  border-radius: var(--radius-xs);
  cursor: pointer;
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-muted);
  border: 1px solid var(--glass-l1-border);
  white-space: nowrap;
  transition: color var(--duration-fast) var(--ease-glass),
    border-color var(--duration-fast) var(--ease-glass),
    background var(--duration-fast) var(--ease-glass);
}
.deploy-btn:hover {
  color: var(--color-accent);
  border-color: rgba(10, 132, 255, 0.4);
  background: rgba(10, 132, 255, 0.08);
}

/* ---- job 區塊 ---- */
.job-body {
  padding: 0 calc(var(--spacing) * 4) calc(var(--spacing) * 4);
}
.job-lead {
  font-size: 12px;
  color: var(--color-text-muted);
  margin: 0 0 calc(var(--spacing) * 3);
}
.actions {
  display: flex;
  gap: calc(var(--spacing) * 2);
}
.job-btn {
  font-size: 12px;
  font-weight: 600;
  padding: calc(var(--spacing) * 1.5) calc(var(--spacing) * 4);
  border-radius: var(--radius-sm);
  cursor: pointer;
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-text);
  border: 1px solid var(--glass-l1-border);
  transition: opacity var(--duration-fast) var(--ease-glass),
    transform var(--duration-fast) var(--ease-glass),
    background var(--duration-fast) var(--ease-glass);
}
.job-btn.primary {
  background: var(--color-accent);
  color: #fff;
  border-color: transparent;
}
.job-btn:hover:not(:disabled) {
  opacity: 0.92;
}
.job-btn:active:not(:disabled) {
  transform: scale(0.97);
}
.job-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.job-status {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 2);
  font-size: 12px;
  color: var(--color-text);
  margin: calc(var(--spacing) * 3) 0 0;
  font-variant-numeric: tabular-nums;
}
.job-status .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-accent);
  flex: none;
}
.job-status .dot[data-status='COMPLETED'],
.job-status .dot[data-status='FINISHED'] {
  background: var(--color-up);
}
.job-status .dot[data-status='FAILED'] {
  background: var(--color-down);
}
.job-hint {
  font-size: 12px;
  color: var(--color-text-faint);
  margin: calc(var(--spacing) * 3) 0 0;
}
</style>
