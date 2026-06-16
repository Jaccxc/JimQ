/**
 * 卡 #23 (W4) — Research 儀表板 composable。
 *
 * 串接 research store 與 REST:
 * - loadModels:載已登記模型列表(GET /models)。
 * - loadExperiments:載 MLflow experiments;若有 experiment 自動載第一個的 runs。
 * - selectExperiment:選某 experiment → 載其 runs(GET /mlflow/runs)。
 * - runJob:觸發 dataset build / 訓練 job(POST /research/jobs)→ 記到
 *   store.lastJob(供 UI 顯示狀態)。
 *
 * api 以參數注入(預設真實 client),測試可注入 fake 達決定論。
 */
import { ref } from 'vue'
import {
  fetchModels as realFetchModels,
  fetchExperiments as realFetchExperiments,
  fetchRuns as realFetchRuns,
  triggerJob as realTriggerJob,
  type ExperimentRecord,
  type JobAccepted,
  type MlflowRun,
  type ModelRecord,
  type TriggerJobRequest,
} from '@/api/research'
import { useResearchStore } from '@/stores/research'

/** 注入點:REST client(預設真實)。 */
export interface ResearchApi {
  fetchModels: () => Promise<ModelRecord[]>
  fetchExperiments: () => Promise<ExperimentRecord[]>
  fetchRuns: (experimentId: string) => Promise<MlflowRun[]>
  triggerJob: (req: TriggerJobRequest) => Promise<JobAccepted>
}

export interface UseResearchOptions {
  api?: Partial<ResearchApi>
}

export function useResearch(opts: UseResearchOptions = {}) {
  const api: ResearchApi = {
    fetchModels: opts.api?.fetchModels ?? (() => realFetchModels()),
    fetchExperiments: opts.api?.fetchExperiments ?? (() => realFetchExperiments()),
    fetchRuns: opts.api?.fetchRuns ?? ((id: string) => realFetchRuns(id)),
    triggerJob: opts.api?.triggerJob ?? ((req: TriggerJobRequest) => realTriggerJob(req)),
  }
  const store = useResearchStore()

  const loadingModels = ref(false)
  const loadingRuns = ref(false)
  const jobPending = ref(false)
  const error = ref<string | null>(null)

  async function loadModels(): Promise<void> {
    loadingModels.value = true
    error.value = null
    try {
      store.setModels(await api.fetchModels())
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loadingModels.value = false
    }
  }

  async function loadRunsFor(experimentId: string): Promise<void> {
    loadingRuns.value = true
    try {
      store.setRuns(await api.fetchRuns(experimentId))
    } finally {
      loadingRuns.value = false
    }
  }

  async function loadExperiments(): Promise<void> {
    error.value = null
    try {
      const experiments = await api.fetchExperiments()
      store.setExperiments(experiments)
      // 有 experiment 時自動選第一個並載其 runs(預設先看一份比較)。
      if (experiments.length > 0) {
        store.selectExperiment(experiments[0].experiment_id)
        await loadRunsFor(experiments[0].experiment_id)
      }
    } catch (e) {
      error.value = (e as Error).message
    }
  }

  async function selectExperiment(experimentId: string): Promise<void> {
    store.selectExperiment(experimentId)
    error.value = null
    try {
      await loadRunsFor(experimentId)
    } catch (e) {
      error.value = (e as Error).message
    }
  }

  async function runJob(
    jobType: TriggerJobRequest['job_type'],
    params: Record<string, unknown>,
  ): Promise<void> {
    jobPending.value = true
    error.value = null
    try {
      const accepted = await api.triggerJob({ job_type: jobType, params })
      store.setLastJob(accepted)
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      jobPending.value = false
    }
  }

  return {
    store,
    loadingModels,
    loadingRuns,
    jobPending,
    error,
    loadModels,
    loadExperiments,
    selectExperiment,
    runJob,
  }
}
