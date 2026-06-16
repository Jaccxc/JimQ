/**
 * 卡 #23 (W4) — Research 儀表板 REST client。
 *
 * - fetchModels:GET /api/v1/models(FastCRUD 分頁 {data,...})→ 取 data[]
 *   (已登記模型:name/version/framework/metrics/created_at)。
 * - fetchExperiments:GET /api/v1/mlflow/experiments → MLflow experiments(api
 *   經 HTTP proxy MLflow REST,前端只看攤平後形狀)。
 * - fetchRuns:GET /api/v1/mlflow/runs?experiment_id= → 該 experiment 的 runs
 *   (params/metrics 已攤平成 dict)。
 * - triggerJob:POST /api/v1/research/jobs → 觸發 dataset build / 訓練 job;
 *   回 {job_id, correlation_id, status}(後端建 PENDING 列 + 發命令到 command
 *   stream)。
 *
 * 走 vite proxy /api → http://127.0.0.1:8000。fetch 可注入(測試決定論)。
 */

/** GET /models 的一列(對齊 api ModelRegistryRead;只取儀表板關心的欄位)。 */
export interface ModelRecord {
  id: number
  name: string
  version: string
  framework: string
  metrics: Record<string, unknown>
  created_at: string
  artifact_path?: string
  training_run_id?: string | null
  sharpe?: string | number | null
}

/** MLflow experiment(攤平後)。 */
export interface ExperimentRecord {
  experiment_id: string
  name: string
  lifecycle_stage?: string
}

/** MLflow run(api 已把 params/metrics 攤平成 dict)。 */
export interface MlflowRun {
  run_id: string
  run_name: string | null
  experiment_id?: string
  status: string
  start_time?: number
  params: Record<string, string>
  metrics: Record<string, number>
}

/** POST /research/jobs 請求 body(對齊 api ResearchJobRequest)。 */
export interface TriggerJobRequest {
  job_type: 'BUILD_DATASET' | 'TRAIN'
  params: Record<string, unknown>
}

/** POST /research/jobs 回應(對齊 api ResearchJobAccepted)。 */
export interface JobAccepted {
  job_id: number
  correlation_id: string
  status: string
}

export interface ClientOptions {
  /** base path 覆寫(預設同源 /api/v1)。 */
  baseUrl?: string
  /** 注入 fetch(測試用)。 */
  fetchImpl?: typeof fetch
}

/** FastCRUD 分頁 envelope(只取 data)。 */
interface Paginated<T> {
  data: T[]
  total_count?: number
}

function resolve(opts: ClientOptions) {
  return { base: opts.baseUrl ?? '/api/v1', f: opts.fetchImpl ?? fetch }
}

export async function fetchModels(opts: ClientOptions = {}): Promise<ModelRecord[]> {
  const { base, f } = resolve(opts)
  const res = await f(`${base}/models?page=1&itemsPerPage=100`)
  if (!res.ok) {
    throw new Error(`fetchModels ${res.status} ${res.statusText ?? ''}`.trim())
  }
  const body = (await res.json()) as Paginated<ModelRecord>
  return body.data ?? []
}

export async function fetchExperiments(opts: ClientOptions = {}): Promise<ExperimentRecord[]> {
  const { base, f } = resolve(opts)
  const res = await f(`${base}/mlflow/experiments`)
  if (!res.ok) {
    throw new Error(`fetchExperiments ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as ExperimentRecord[]
}

export async function fetchRuns(
  experimentId: string,
  opts: ClientOptions = {},
): Promise<MlflowRun[]> {
  const { base, f } = resolve(opts)
  const res = await f(`${base}/mlflow/runs?experiment_id=${encodeURIComponent(experimentId)}`)
  if (!res.ok) {
    throw new Error(`fetchRuns ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as MlflowRun[]
}

export async function triggerJob(
  req: TriggerJobRequest,
  opts: ClientOptions = {},
): Promise<JobAccepted> {
  const { base, f } = resolve(opts)
  const res = await f(`${base}/research/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    throw new Error(`triggerJob ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as JobAccepted
}
