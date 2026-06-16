/**
 * 卡 #24 (W5) — 策略控制平面行為測試(api client + store + composable)。
 *
 * 只驗 public interface 行為(不驗 DOM/實作細節):
 * - api/control:startStrategy / stopStrategy / killAll → POST 到對應端點,
 *   回 {strategy_id, command_type, correlation_id}。
 * - stores/strategyControl:追蹤目前控制狀態(lastCommand / killed)。
 * - composables/useStrategyControl:start/stop/kill → 呼叫 api → 寫 store;
 *   失敗時記 error。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import { startStrategy, stopStrategy, killAll } from '@/api/control'
import { useStrategyControlStore } from '@/stores/strategyControl'
import { useStrategyControl } from '@/composables/useStrategyControl'

beforeEach(() => setActivePinia(createPinia()))

function okFetch(body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 202,
    json: async () => body,
  }) as unknown as typeof fetch
}

describe('api/control', () => {
  it('startStrategy POSTs to /strategies/{id}/start with params', async () => {
    const fetchMock = okFetch({
      strategy_id: 'ema_cross',
      command_type: 'START_STRATEGY',
      correlation_id: 'c1',
    })
    const res = await startStrategy(
      'ema_cross',
      { fast_period: 3 },
      { baseUrl: '/api/v1', fetchImpl: fetchMock },
    )
    expect(res.command_type).toBe('START_STRATEGY')
    expect(res.strategy_id).toBe('ema_cross')
    const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/v1/strategies/ema_cross/start')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ params: { fast_period: 3 } })
  })

  it('stopStrategy POSTs to /strategies/{id}/stop', async () => {
    const fetchMock = okFetch({
      strategy_id: 'ema_cross',
      command_type: 'STOP_STRATEGY',
      correlation_id: 'c2',
    })
    const res = await stopStrategy('ema_cross', { baseUrl: '/api/v1', fetchImpl: fetchMock })
    expect(res.command_type).toBe('STOP_STRATEGY')
    const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/v1/strategies/ema_cross/stop')
    expect(init.method).toBe('POST')
  })

  it('killAll POSTs to /kill', async () => {
    const fetchMock = okFetch({
      strategy_id: null,
      command_type: 'KILL',
      correlation_id: 'c3',
    })
    const res = await killAll({ baseUrl: '/api/v1', fetchImpl: fetchMock })
    expect(res.command_type).toBe('KILL')
    const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/v1/kill')
    expect(init.method).toBe('POST')
  })

  it('throws on non-ok response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'err',
    }) as unknown as typeof fetch
    await expect(killAll({ fetchImpl: fetchMock })).rejects.toThrow()
  })
})

describe('stores/strategyControl', () => {
  it('records last command and kill state', () => {
    const store = useStrategyControlStore()
    expect(store.lastCommand).toBeNull()
    expect(store.killed).toBe(false)
    store.recordCommand({ strategy_id: 'ema_cross', command_type: 'START_STRATEGY', correlation_id: 'c1' })
    expect(store.lastCommand?.command_type).toBe('START_STRATEGY')
    store.recordCommand({ strategy_id: null, command_type: 'KILL', correlation_id: 'c2' })
    expect(store.killed).toBe(true)
  })
})

describe('composables/useStrategyControl', () => {
  it('start calls api and records to store', async () => {
    const api = {
      startStrategy: vi.fn().mockResolvedValue({
        strategy_id: 'ema_cross',
        command_type: 'START_STRATEGY',
        correlation_id: 'c1',
      }),
    }
    const ctrl = useStrategyControl({ api })
    await ctrl.start('ema_cross', { fast_period: 3 })
    expect(api.startStrategy).toHaveBeenCalledWith('ema_cross', { fast_period: 3 })
    expect(ctrl.store.lastCommand?.command_type).toBe('START_STRATEGY')
  })

  it('kill calls api and flips killed', async () => {
    const api = {
      killAll: vi.fn().mockResolvedValue({
        strategy_id: null,
        command_type: 'KILL',
        correlation_id: 'c3',
      }),
    }
    const ctrl = useStrategyControl({ api })
    await ctrl.kill()
    expect(api.killAll).toHaveBeenCalled()
    expect(ctrl.store.killed).toBe(true)
  })

  it('records error on api failure', async () => {
    const api = { killAll: vi.fn().mockRejectedValue(new Error('boom')) }
    const ctrl = useStrategyControl({ api })
    await ctrl.kill()
    expect(ctrl.error.value).toBe('boom')
  })
})
