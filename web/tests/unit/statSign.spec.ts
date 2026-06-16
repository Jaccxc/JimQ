/**
 * 改版 S1b — StatPill 漲跌方向衍生邏輯(純函式,決定論)。
 * 正→up、負→down、0/NaN→flat;供 StatPill 與其他數字色塊覆用。
 */
import { describe, it, expect } from 'vitest'
import { statSign } from '@/lib/utils'

describe('statSign()', () => {
  it('正數 → up', () => {
    expect(statSign(0.01)).toBe('up')
    expect(statSign(1234)).toBe('up')
  })

  it('負數 → down', () => {
    expect(statSign(-0.01)).toBe('down')
  })

  it('0 → flat', () => {
    expect(statSign(0)).toBe('flat')
    expect(statSign(-0)).toBe('flat')
  })

  it('NaN → flat(避免錯誤上色)', () => {
    expect(statSign(NaN)).toBe('flat')
  })
})
