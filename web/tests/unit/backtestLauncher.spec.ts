/**
 * 卡 #20 (W1) — backtest launcher 行為測試(api client + store + composable)。
 *
 * 只驗 public interface 行為(不驗 DOM/實作細節):
 * - api/backtests.runBacktest:POST /backtests/run,回 {run_id, correlation_id, status}。
 * - stores/backtestRun:追蹤目前 run(id/correlation/status),markRunning/setStatus。
 * - composables/useBacktestLauncher.launch:組請求 -> runBacktest -> 寫 store ->
 *   回 run_id;失敗時 store 標 error。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import { runBacktest, fetchBacktestRun } from '@/api/backtests'
import { useBacktestRunStore } from '@/stores/backtestRun'
import { useBacktestLauncher } from '@/composables/useBacktestLauncher'

beforeEach(() => setActivePinia(createPinia()))

describe('api/backtests', () => {
  it('runBacktest POSTs to /backtests/run and returns accepted body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({ run_id: 7, correlation_id: 'corr-7', status: 'PENDING' }),
    })
    const res = await runBacktest(
      {
        symbol: 'BTCUSDT-PERP.BINANCE',
        timeframe: '1m',
        strategy: 'ema_cross',
        params: { fast_period: 3, slow_period: 8 },
        start: '2023-11-14T22:13:20Z',
        end: '2023-11-14T22:46:20Z',
      },
      { baseUrl: '/api/v1', fetchImpl: fetchMock as unknown as typeof fetch },
    )
    expect(res.run_id).toBe(7)
    expect(res.correlation_id).toBe('corr-7')
    expect(res.status).toBe('PENDING')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/backtests/run')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body)
    expect(body.strategy).toBe('ema_cross')
    expect(body.params).toEqual({ fast_period: 3, slow_period: 8 })
  })

  it('runBacktest throws on non-ok response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable',
      json: async () => ({}),
    })
    await expect(
      runBacktest(
        { symbol: 'X', timeframe: '1m', strategy: 'ema_cross', params: {}, start: 'a', end: 'b' },
        { fetchImpl: fetchMock as unknown as typeof fetch },
      ),
    ).rejects.toThrow()
  })

  it('fetchBacktestRun GETs /backtests/{id}', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 7, status: 'COMPLETED', num_trades: 3 }),
    })
    const run = await fetchBacktestRun(7, {
      baseUrl: '/api/v1',
      fetchImpl: fetchMock as unknown as typeof fetch,
    })
    expect(run.status).toBe('COMPLETED')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/backtests/7')
  })
})

describe('stores/backtestRun', () => {
  it('starts idle, tracks run id/correlation/status', () => {
    const s = useBacktestRunStore()
    expect(s.runId).toBeNull()
    expect(s.status).toBe('IDLE')
    s.startRun({ run_id: 9, correlation_id: 'c-9', status: 'PENDING' })
    expect(s.runId).toBe(9)
    expect(s.correlationId).toBe('c-9')
    expect(s.status).toBe('PENDING')
    expect(s.isActive).toBe(true)
    s.setStatus('COMPLETED')
    expect(s.status).toBe('COMPLETED')
    expect(s.isActive).toBe(false)
  })

  it('fail() records error and FAILED status', () => {
    const s = useBacktestRunStore()
    s.fail('boom')
    expect(s.status).toBe('FAILED')
    expect(s.error).toBe('boom')
  })
})

describe('composables/useBacktestLauncher', () => {
  it('launch posts the form, stores the run, returns run_id', async () => {
    const runMock = vi
      .fn()
      .mockResolvedValue({ run_id: 11, correlation_id: 'c-11', status: 'PENDING' })
    const launcher = useBacktestLauncher({ runImpl: runMock })
    const runId = await launcher.launch({
      symbol: 'BTCUSDT-PERP.BINANCE',
      timeframe: '1m',
      strategy: 'ema_cross',
      params: { fast_period: 3, slow_period: 8 },
      start: '2023-11-14T22:13:20Z',
      end: '2023-11-14T22:46:20Z',
    })
    expect(runId).toBe(11)
    const s = useBacktestRunStore()
    expect(s.runId).toBe(11)
    expect(s.status).toBe('PENDING')
    expect(runMock).toHaveBeenCalledOnce()
  })

  it('launch on error marks store FAILED and rethrows', async () => {
    const runMock = vi.fn().mockRejectedValue(new Error('network'))
    const launcher = useBacktestLauncher({ runImpl: runMock })
    await expect(
      launcher.launch({
        symbol: 'X',
        timeframe: '1m',
        strategy: 'ema_cross',
        params: {},
        start: 'a',
        end: 'b',
      }),
    ).rejects.toThrow('network')
    expect(useBacktestRunStore().status).toBe('FAILED')
  })
})
