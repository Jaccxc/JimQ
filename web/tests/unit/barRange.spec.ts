/**
 * Backtest 開箱即用 — bar range client + 動態預設日期。
 *
 * 只驗 public interface 行為:
 * - api/bars.fetchBarRange:GET /bars/range?symbol=&timeframe=,回 {start,end,count}。
 * - composables/useBacktestLauncher.defaultRange:把 range 轉成 datetime-local
 *   字串 {start,end},catalog 有資料時取**最後一段足夠長**的範圍(確保夠 EMA
 *   交叉產生成交);空 catalog 時回 fallback。
 */
import { describe, it, expect, vi } from 'vitest'

import { fetchBarRange } from '@/api/bars'
import { defaultRange } from '@/composables/useBacktestLauncher'

describe('api/bars.fetchBarRange', () => {
  it('GETs /bars/range with symbol+timeframe and returns span', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ start: 1704067200000000000, end: 1704153600000000000, count: 1441 }),
    })
    const r = await fetchBarRange(
      { symbol: 'BTCUSDT-PERP.BINANCE', timeframe: '1m', baseUrl: '/api/v1' },
      fetchMock as unknown as typeof fetch,
    )
    expect(r.count).toBe(1441)
    expect(r.start).toBe(1704067200000000000)
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/api/v1/bars/range')
    expect(url).toContain('symbol=BTCUSDT-PERP.BINANCE')
    expect(url).toContain('timeframe=1m')
  })
})

describe('defaultRange', () => {
  it('maps a populated range to datetime-local start/end (UTC minute precision)', () => {
    // 2024-01-01T00:00 .. 2024-01-02T00:00 UTC, ns epoch
    const startNs = Date.UTC(2024, 0, 1, 0, 0, 0) * 1_000_000
    const endNs = Date.UTC(2024, 0, 2, 0, 0, 0) * 1_000_000
    const { start, end, hasData } = defaultRange({ start: startNs, end: endNs, count: 1441 })
    expect(hasData).toBe(true)
    expect(end).toBe('2024-01-02T00:00')
    // 取最後一段(足夠長):start <= end, 仍在資料區間內
    expect(start <= end).toBe(true)
    expect(start >= '2024-01-01T00:00').toBe(true)
    // datetime-local 格式 YYYY-MM-DDTHH:mm
    expect(start).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
  })

  it('returns hasData=false fallback when catalog is empty', () => {
    const { hasData, start, end } = defaultRange({ start: null, end: null, count: 0 })
    expect(hasData).toBe(false)
    expect(start).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(end).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(start < end).toBe(true)
  })
})
