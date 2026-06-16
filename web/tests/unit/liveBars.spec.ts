/**
 * 卡 #30 (P2-S1b) — Live 頁近期真 klines API client(fetchLiveBars)。
 *
 * 行為(public interface):
 * - 打 GET /api/v1/live/bars,帶 symbol / timeframe / limit query。
 * - 回 BarDTO[](後端已映射 testnet 公開 klines → BarDTO 形狀)。
 * - 非 2xx → throw(呼叫端 fallback / 顯示連線問題)。
 *
 * 只驗 client 行為,不打真網路(注入 fake fetch)。
 */
import { describe, it, expect, vi } from 'vitest'
import { fetchLiveBars } from '@/api/bars'
import type { BarDTO } from '@/types/contract'

const NS = 1_000_000_000
function bar(time: number, close: number): BarDTO {
  return {
    ts: time * NS,
    time,
    open: String(close),
    high: String(close + 1),
    low: String(close - 1),
    close: String(close),
    volume: '1',
  }
}

describe('fetchLiveBars', () => {
  it('打 /api/v1/live/bars 帶 symbol/timeframe/limit 並回 BarDTO[]', async () => {
    const payload = [bar(1000, 66000), bar(1060, 66005)]
    const fakeFetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => payload,
    })) as unknown as typeof fetch

    const out = await fetchLiveBars(
      { symbol: 'BTCUSDT-PERP.BINANCE', timeframe: '1m', limit: 200 },
      fakeFetch,
    )

    expect(out).toEqual(payload)
    expect(fakeFetch).toHaveBeenCalledTimes(1)
    const url = (fakeFetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain('/live/bars')
    expect(url).toContain('symbol=BTCUSDT-PERP.BINANCE')
    expect(url).toContain('timeframe=1m')
    expect(url).toContain('limit=200')
  })

  it('非 2xx → throw', async () => {
    const fakeFetch = vi.fn(async () => ({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => [],
    })) as unknown as typeof fetch

    await expect(
      fetchLiveBars({ symbol: 'BTCUSDT-PERP.BINANCE' }, fakeFetch),
    ).rejects.toThrow()
  })
})
