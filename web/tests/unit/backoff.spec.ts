/**
 * 行為測試:WS 重連退避(指數退避 + jitter,有上限)。
 */
import { describe, it, expect } from 'vitest'
import { nextBackoffMs, BACKOFF_BASE_MS, BACKOFF_MAX_MS } from '@/lib/backoff'

describe('nextBackoffMs', () => {
  // 用固定 rng=0 抽掉 jitter,驗指數骨架。
  const noJitter = () => 0

  it('第 0 次嘗試 = base', () => {
    expect(nextBackoffMs(0, noJitter)).toBe(BACKOFF_BASE_MS)
  })

  it('指數成長:attempt n = base * 2^n(未到上限)', () => {
    expect(nextBackoffMs(1, noJitter)).toBe(BACKOFF_BASE_MS * 2)
    expect(nextBackoffMs(2, noJitter)).toBe(BACKOFF_BASE_MS * 4)
    expect(nextBackoffMs(3, noJitter)).toBe(BACKOFF_BASE_MS * 8)
  })

  it('封頂在 BACKOFF_MAX_MS', () => {
    expect(nextBackoffMs(100, noJitter)).toBe(BACKOFF_MAX_MS)
  })

  it('jitter 加在退避之上,落在 [base*2^n, base*2^n + 上限基數) 區間且不超過 MAX', () => {
    // rng=1(接近上界)。
    const v = nextBackoffMs(1, () => 0.999)
    const floor = BACKOFF_BASE_MS * 2
    expect(v).toBeGreaterThanOrEqual(floor)
    expect(v).toBeLessThanOrEqual(BACKOFF_MAX_MS)
  })

  it('jitter 非負且具隨機性(不同 rng 給不同值)', () => {
    const a = nextBackoffMs(2, () => 0.1)
    const b = nextBackoffMs(2, () => 0.9)
    expect(a).not.toBe(b)
    expect(a).toBeGreaterThanOrEqual(BACKOFF_BASE_MS * 4)
    expect(b).toBeGreaterThanOrEqual(BACKOFF_BASE_MS * 4)
  })
})
