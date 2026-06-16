/**
 * 卡 #23 (W4) — Research 儀表板:行為測試。
 *
 * 涵蓋(只驗 public interface,注入 fetch 決定論):
 *  - api/research client:fetchModels(GET /models,FastCRUD 分頁 → data[])、
 *    fetchExperiments / fetchRuns(MLflow proxy)、triggerJob(POST /research/jobs)。
 *  - stores/research store:setModels / setExperiments / selectExperiment /
 *    setRuns / job 觸發狀態(lastJob)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

beforeEach(() => setActivePinia(createPinia()))

function fakeFetch(payload: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'ERR',
    json: async () => payload,
  } as Response)
}

describe('api/research client', () => {
  it('fetchModels:取 FastCRUD 分頁 data[]', async () => {
    const { fetchModels } = await import('@/api/research')
    const f = fakeFetch({
      data: [
        {
          id: 1,
          name: 'ppo_btc_perp',
          version: 'v1',
          framework: 'STABLE_BASELINES3',
          metrics: { sharpe: 1.4 },
          created_at: '2026-06-16T00:00:00Z',
        },
      ],
      total_count: 1,
    })
    const models = await fetchModels({ fetchImpl: f })
    expect(models).toHaveLength(1)
    expect(models[0].name).toBe('ppo_btc_perp')
    expect(String(f.mock.calls[0][0])).toContain('/models')
  })

  it('fetchExperiments:回 experiment 陣列', async () => {
    const { fetchExperiments } = await import('@/api/research')
    const f = fakeFetch([
      { experiment_id: '1', name: 'backtest' },
      { experiment_id: '2', name: 'train' },
    ])
    const exps = await fetchExperiments({ fetchImpl: f })
    expect(exps.map((e) => e.name)).toEqual(['backtest', 'train'])
    expect(String(f.mock.calls[0][0])).toContain('/mlflow/experiments')
  })

  it('fetchRuns:帶 experiment_id 查並回攤平 runs', async () => {
    const { fetchRuns } = await import('@/api/research')
    const f = fakeFetch([
      {
        run_id: 'abc',
        run_name: 'ema-3-8',
        status: 'FINISHED',
        params: { fast_period: '3' },
        metrics: { sharpe: 1.5 },
      },
    ])
    const runs = await fetchRuns('1', { fetchImpl: f })
    expect(runs[0].run_id).toBe('abc')
    expect(runs[0].metrics.sharpe).toBe(1.5)
    expect(String(f.mock.calls[0][0])).toContain('experiment_id=1')
  })

  it('triggerJob:POST /research/jobs 回 {job_id,...}', async () => {
    const { triggerJob } = await import('@/api/research')
    const f = fakeFetch({ job_id: 77, correlation_id: 'corr-1', status: 'PENDING' })
    const acc = await triggerJob(
      { job_type: 'BUILD_DATASET', params: { symbol: 'BTCUSDT-PERP.BINANCE' } },
      { fetchImpl: f },
    )
    expect(acc.job_id).toBe(77)
    expect(acc.status).toBe('PENDING')
    const [url, init] = f.mock.calls[0]
    expect(String(url)).toContain('/research/jobs')
    expect((init as RequestInit).method).toBe('POST')
    const sent = JSON.parse((init as RequestInit).body as string)
    expect(sent.job_type).toBe('BUILD_DATASET')
  })

  it('client 在非 2xx 時丟錯', async () => {
    const { fetchModels } = await import('@/api/research')
    const f = fakeFetch({}, false)
    await expect(fetchModels({ fetchImpl: f })).rejects.toThrow()
  })
})

describe('research store', () => {
  it('setModels 載入模型列表', async () => {
    const { useResearchStore } = await import('@/stores/research')
    const s = useResearchStore()
    s.setModels([
      {
        id: 1,
        name: 'm',
        version: 'v1',
        framework: 'TORCH',
        metrics: {},
        created_at: '2026-06-16T00:00:00Z',
      },
    ])
    expect(s.models).toHaveLength(1)
  })

  it('selectExperiment 設定目前 experiment 並清空舊 runs', async () => {
    const { useResearchStore } = await import('@/stores/research')
    const s = useResearchStore()
    s.setExperiments([{ experiment_id: '1', name: 'backtest' }])
    s.setRuns([
      { run_id: 'old', run_name: null, status: 'FINISHED', params: {}, metrics: {} },
    ])
    s.selectExperiment('1')
    expect(s.selectedExperimentId).toBe('1')
    expect(s.runs).toHaveLength(0) // 換 experiment 先清舊 runs
  })

  it('setRuns 存目前 experiment 的 runs', async () => {
    const { useResearchStore } = await import('@/stores/research')
    const s = useResearchStore()
    s.setRuns([
      { run_id: 'abc', run_name: 'r', status: 'FINISHED', params: {}, metrics: { sharpe: 1 } },
    ])
    expect(s.runs[0].run_id).toBe('abc')
  })

  it('setLastJob 記錄最近一次觸發的 job(供 UI 顯示狀態)', async () => {
    const { useResearchStore } = await import('@/stores/research')
    const s = useResearchStore()
    s.setLastJob({ job_id: 77, correlation_id: 'c', status: 'PENDING' })
    expect(s.lastJob?.job_id).toBe(77)
    expect(s.lastJob?.status).toBe('PENDING')
  })
})

describe('useResearch composable', () => {
  it('loadModels:呼叫 api.fetchModels 並填 store', async () => {
    const { useResearch } = await import('@/composables/useResearch')
    const fetchModels = vi.fn().mockResolvedValue([
      {
        id: 1,
        name: 'm',
        version: 'v1',
        framework: 'TORCH',
        metrics: {},
        created_at: '2026-06-16T00:00:00Z',
      },
    ])
    const r = useResearch({
      api: {
        fetchModels,
        fetchExperiments: vi.fn().mockResolvedValue([]),
        fetchRuns: vi.fn().mockResolvedValue([]),
        triggerJob: vi.fn(),
      },
    })
    await r.loadModels()
    expect(fetchModels).toHaveBeenCalledOnce()
    expect(r.store.models).toHaveLength(1)
  })

  it('loadExperiments:填 experiments;有 experiment 時自動載第一個的 runs', async () => {
    const { useResearch } = await import('@/composables/useResearch')
    const fetchExperiments = vi
      .fn()
      .mockResolvedValue([{ experiment_id: '1', name: 'backtest' }])
    const fetchRuns = vi.fn().mockResolvedValue([
      { run_id: 'abc', run_name: 'r', status: 'FINISHED', params: {}, metrics: {} },
    ])
    const r = useResearch({
      api: { fetchModels: vi.fn(), fetchExperiments, fetchRuns, triggerJob: vi.fn() },
    })
    await r.loadExperiments()
    expect(r.store.experiments).toHaveLength(1)
    expect(fetchRuns).toHaveBeenCalledWith('1')
    expect(r.store.runs).toHaveLength(1)
  })

  it('selectExperiment:載該 experiment 的 runs', async () => {
    const { useResearch } = await import('@/composables/useResearch')
    const fetchRuns = vi.fn().mockResolvedValue([
      { run_id: 'x', run_name: 'r', status: 'FINISHED', params: {}, metrics: {} },
    ])
    const r = useResearch({
      api: {
        fetchModels: vi.fn(),
        fetchExperiments: vi.fn().mockResolvedValue([{ experiment_id: '2', name: 'train' }]),
        fetchRuns,
        triggerJob: vi.fn(),
      },
    })
    await r.selectExperiment('2')
    expect(r.store.selectedExperimentId).toBe('2')
    expect(fetchRuns).toHaveBeenCalledWith('2')
    expect(r.store.runs).toHaveLength(1)
  })

  it('runJob:呼叫 api.triggerJob 並記到 store.lastJob', async () => {
    const { useResearch } = await import('@/composables/useResearch')
    const triggerJob = vi
      .fn()
      .mockResolvedValue({ job_id: 5, correlation_id: 'c', status: 'PENDING' })
    const r = useResearch({
      api: {
        fetchModels: vi.fn(),
        fetchExperiments: vi.fn(),
        fetchRuns: vi.fn(),
        triggerJob,
      },
    })
    await r.runJob('TRAIN', { model: 'baseline' })
    expect(triggerJob).toHaveBeenCalledWith({ job_type: 'TRAIN', params: { model: 'baseline' } })
    expect(r.store.lastJob?.job_id).toBe(5)
  })
})
