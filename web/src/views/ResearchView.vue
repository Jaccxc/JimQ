<script setup lang="ts">
/**
 * 卡 #23 (W4) — Research 頁(/research)研究儀表板。
 *
 * 三塊:
 *  1. Models:已登記模型列表(GET /api/v1/models)— name/version/framework/
 *     metrics/created_at 表格。
 *  2. MLflow runs:某 experiment 的 runs(經 api MLflow proxy)— params/metrics
 *     比較表;可切換 experiment。
 *  3. 觸發 job:從 web 觸發 dataset build / 訓練 job(POST /api/v1/research/jobs)
 *     → 顯示回傳的 job 狀態(MVP:job 被觸發並可看狀態)。
 *
 * 資料/觸發走 useResearch composable(api 可由 prop 注入,測試決定論)。掛載時
 * appMode.setBacktest()(研究操作歷史/registry 資料,非 live testnet)。
 */
import { onMounted, computed } from 'vue'
import { useResearch, type ResearchApi } from '@/composables/useResearch'
import { useAppModeStore } from '@/stores/appMode'

const props = defineProps<{ api?: Partial<ResearchApi> }>()

const appMode = useAppModeStore()
const research = useResearch({ api: props.api })
const store = research.store

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

onMounted(async () => {
  appMode.setBacktest()
  await Promise.all([research.loadModels(), research.loadExperiments()])
})
</script>

<template>
  <div class="research" data-testid="research-dashboard">
    <header class="topbar"><h1>Research</h1></header>

    <main class="grid">
      <!-- 1) 已登記模型 -->
      <section class="panel">
        <h2>Models</h2>
        <table class="tbl" data-testid="models-table">
          <thead>
            <tr><th>name</th><th>version</th><th>framework</th><th>sharpe</th><th>created_at</th></tr>
          </thead>
          <tbody>
            <tr v-for="m in store.models" :key="m.id">
              <td>{{ m.name }}</td>
              <td>{{ m.version }}</td>
              <td>{{ m.framework }}</td>
              <td>{{ m.sharpe ?? '—' }}</td>
              <td>{{ m.created_at }}</td>
            </tr>
            <tr v-if="store.models.length === 0" class="empty">
              <td colspan="5">尚無已登記模型</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 2) MLflow runs 比較 -->
      <section class="panel">
        <div class="panel-head">
          <h2>MLflow runs</h2>
          <select
            v-if="store.experiments.length"
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
        <table class="tbl" data-testid="mlflow-runs-table">
          <thead>
            <tr>
              <th>run</th><th>status</th>
              <th v-for="k in metricKeys" :key="k">{{ k }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in store.runs" :key="r.run_id">
              <td>{{ r.run_name ?? r.run_id }}</td>
              <td>{{ r.status }}</td>
              <td v-for="k in metricKeys" :key="k">{{ fmt(r.metrics[k]) }}</td>
            </tr>
            <tr v-if="store.runs.length === 0" class="empty">
              <td :colspan="2 + metricKeys.length">尚無 runs(連 MLflow 服務後顯示)</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 3) 觸發 job -->
      <section class="panel">
        <h2>觸發 job</h2>
        <div class="actions">
          <button
            type="button"
            class="job-btn"
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
          job #{{ store.lastJob.job_id }} — {{ store.lastJob.status }}
        </p>
        <p v-else class="job-hint">觸發後在此顯示 job id 與狀態。</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.research { display: flex; flex-direction: column; height: 100%; overflow-y: auto; background: #0e1117; }
.topbar { padding: 8px 16px; border-bottom: 1px solid #1c2230; }
.topbar h1 { font-size: 14px; color: #d1d4dc; margin: 0; font-weight: 600; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; }
.panel { background: #11151d; border: 1px solid #1c2230; border-radius: 8px; padding: 12px; }
.panel:first-child { grid-column: 1 / -1; }
.panel-head { display: flex; align-items: center; justify-content: space-between; }
.panel h2 { font-size: 13px; color: #d1d4dc; margin: 0 0 8px; font-weight: 600; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12px; color: #c9ccd6; }
.tbl th { text-align: left; color: #7d8597; font-weight: 600; padding: 4px 8px; border-bottom: 1px solid #1c2230; }
.tbl td { padding: 4px 8px; border-bottom: 1px solid #161b25; }
.tbl tr.empty td { color: #6b7280; text-align: center; padding: 12px; }
.exp-select { background: #0e1117; color: #c9ccd6; border: 1px solid #1c2230; border-radius: 4px; font-size: 12px; padding: 2px 6px; }
.actions { display: flex; gap: 8px; }
.job-btn {
  font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 6px; cursor: pointer;
  background: #1f2937; color: #93c5fd; border: 1px solid #334155;
}
.job-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.job-status { font-size: 12px; color: #34d399; margin: 10px 0 0; }
.job-hint { font-size: 12px; color: #6b7280; margin: 10px 0 0; }
</style>
