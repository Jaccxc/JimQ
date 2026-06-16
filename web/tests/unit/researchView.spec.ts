/**
 * 卡 #23 (W4) — ResearchView 元件行為測試。
 *
 * 驗 Research 頁三塊渲染 + 觸發按鈕行為(注入 fake api 達決定論;只驗 DOM 行為):
 *  - Models 表:每個模型一列(name/version/framework/created_at)。
 *  - MLflow runs 表:每個 run 一列(run/status + 指標)。
 *  - 觸發 job 面板:按鈕觸發後顯示回傳的 job 狀態。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import ResearchView from '@/views/ResearchView.vue'
import { useResearchStore } from '@/stores/research'

beforeEach(() => setActivePinia(createPinia()))

const MODELS = [
  {
    id: 1,
    name: 'ppo_btc_perp',
    version: 'v1',
    framework: 'STABLE_BASELINES3',
    metrics: { sharpe: 1.4 },
    created_at: '2026-06-16T00:00:00Z',
  },
]
const EXPERIMENTS = [{ experiment_id: '1', name: 'backtest' }]
const RUNS = [
  {
    run_id: 'abc123',
    run_name: 'ema-3-8',
    status: 'FINISHED',
    params: { fast_period: '3', slow_period: '8' },
    metrics: { sharpe: 1.5, total_return: 0.1 },
  },
]

function mountView(triggerJob = vi.fn().mockResolvedValue({ job_id: 9, correlation_id: 'c', status: 'PENDING' })) {
  return mount(ResearchView, {
    props: {
      api: {
        fetchModels: vi.fn().mockResolvedValue(MODELS),
        fetchExperiments: vi.fn().mockResolvedValue(EXPERIMENTS),
        fetchRuns: vi.fn().mockResolvedValue(RUNS),
        triggerJob,
      },
    },
  })
}

describe('ResearchView', () => {
  it('掛載後 Models 表每個模型一列', async () => {
    const w = mountView()
    await flushPromises()
    const rows = w.findAll('[data-testid="models-table"] tbody tr')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('ppo_btc_perp')
    expect(rows[0].text()).toContain('STABLE_BASELINES3')
  })

  it('掛載後 MLflow runs 表渲染選取 experiment 的 runs', async () => {
    const w = mountView()
    await flushPromises()
    const rows = w.findAll('[data-testid="mlflow-runs-table"] tbody tr')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('ema-3-8')
    expect(rows[0].text()).toContain('FINISHED')
  })

  it('觸發 job 按鈕呼叫 api.triggerJob 並顯示回傳狀態', async () => {
    const triggerJob = vi
      .fn()
      .mockResolvedValue({ job_id: 42, correlation_id: 'corr', status: 'PENDING' })
    const w = mountView(triggerJob)
    await flushPromises()
    await w.get('[data-testid="trigger-build-dataset"]').trigger('click')
    await flushPromises()
    expect(triggerJob).toHaveBeenCalledOnce()
    const status = w.get('[data-testid="last-job-status"]')
    expect(status.text()).toContain('42')
    expect(status.text()).toContain('PENDING')
  })

  it('store 有資料時不需 api(渲染來自 store)', async () => {
    const w = mountView()
    await flushPromises()
    const store = useResearchStore()
    expect(store.models).toHaveLength(1)
    expect(store.runs).toHaveLength(1)
  })
})
