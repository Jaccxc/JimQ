/**
 * 卡 #23 (W4) — Research 儀表板 store。
 *
 * 持有:已登記模型列表、MLflow experiments + 目前選取 experiment 的 runs、
 * 最近一次觸發的 job(供 UI 顯示狀態)。視圖據此渲染三塊:Models 表、MLflow
 * runs 比較表、觸發 job 面板。
 */
import { defineStore } from 'pinia'
import type {
  ExperimentRecord,
  JobAccepted,
  MlflowRun,
  ModelRecord,
} from '@/api/research'

interface State {
  models: ModelRecord[]
  experiments: ExperimentRecord[]
  selectedExperimentId: string | null
  runs: MlflowRun[]
  lastJob: JobAccepted | null
}

export const useResearchStore = defineStore('research', {
  state: (): State => ({
    models: [],
    experiments: [],
    selectedExperimentId: null,
    runs: [],
    lastJob: null,
  }),
  getters: {
    selectedExperiment(s): ExperimentRecord | null {
      return s.experiments.find((e) => e.experiment_id === s.selectedExperimentId) ?? null
    },
  },
  actions: {
    setModels(models: ModelRecord[]) {
      this.models = models
    },
    setExperiments(experiments: ExperimentRecord[]) {
      this.experiments = experiments
    },
    selectExperiment(experimentId: string) {
      this.selectedExperimentId = experimentId
      this.runs = [] // 換 experiment 先清舊 runs,避免殘留。
    },
    setRuns(runs: MlflowRun[]) {
      this.runs = runs
    },
    setLastJob(job: JobAccepted) {
      this.lastJob = job
    },
  },
})
