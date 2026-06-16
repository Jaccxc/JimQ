/**
 * 改版 S1b — cn() 工具(clsx + tailwind-merge)。
 * shadcn-vue 元件全靠它合併 class;驗證 conditional + tailwind 衝突去重行為。
 */
import { describe, it, expect } from 'vitest'
import { cn } from '@/lib/utils'

describe('cn()', () => {
  it('串接多個 class', () => {
    expect(cn('a', 'b')).toBe('a b')
  })

  it('過濾 falsy(條件式 class)', () => {
    expect(cn('a', false && 'b', undefined, null, 'c')).toBe('a c')
  })

  it('tailwind 衝突時後者覆蓋(merge 去重)', () => {
    expect(cn('px-2 px-4')).toBe('px-4')
    expect(cn('text-text', 'text-text-muted')).toBe('text-text-muted')
  })

  it('支援陣列 / 物件(clsx 語法)', () => {
    expect(cn(['a', 'b'], { c: true, d: false })).toBe('a b c')
  })
})
