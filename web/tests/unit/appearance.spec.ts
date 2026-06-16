/**
 * 行為測試:appearance store(背景外觀選擇 + persist + 套用到根元素)。
 *
 * 公開行為:
 * - 內建 5 種背景選項清單(id/label),預設選最能展示玻璃的一種。
 * - setBackground(id) 更新 current 並寫 localStorage(persist)。
 * - reload(重建 store)時從 localStorage 還原上次選擇(restore)。
 * - 套用機制把 current 寫到 document 根元素 data-bg attribute。
 * - 不合法 id 不改變 current(防壞值)。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  useAppearanceStore,
  BACKGROUNDS,
  DEFAULT_BACKGROUND,
  BACKGROUND_STORAGE_KEY,
} from '@/stores/appearance'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  document.documentElement.removeAttribute('data-bg')
})

describe('appearance store — 背景清單', () => {
  it('提供正好 5 種背景選項,各有 id 與 label', () => {
    expect(BACKGROUNDS).toHaveLength(5)
    for (const b of BACKGROUNDS) {
      expect(typeof b.id).toBe('string')
      expect(b.id.length).toBeGreaterThan(0)
      expect(typeof b.label).toBe('string')
      expect(b.label.length).toBeGreaterThan(0)
    }
    // id 不重複
    const ids = BACKGROUNDS.map((b) => b.id)
    expect(new Set(ids).size).toBe(5)
  })

  it('預設背景是清單內合法 id', () => {
    expect(BACKGROUNDS.map((b) => b.id)).toContain(DEFAULT_BACKGROUND)
  })
})

describe('appearance store — 選擇與 persist', () => {
  it('初始 current = 預設背景', () => {
    const s = useAppearanceStore()
    expect(s.current).toBe(DEFAULT_BACKGROUND)
  })

  it('setBackground 更新 current', () => {
    const s = useAppearanceStore()
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    s.setBackground(target)
    expect(s.current).toBe(target)
  })

  it('setBackground 寫入 localStorage(persist)', () => {
    const s = useAppearanceStore()
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    s.setBackground(target)
    expect(localStorage.getItem(BACKGROUND_STORAGE_KEY)).toBe(target)
  })

  it('不合法 id 不改變 current', () => {
    const s = useAppearanceStore()
    s.setBackground('not-a-real-bg')
    expect(s.current).toBe(DEFAULT_BACKGROUND)
  })
})

describe('appearance store — restore', () => {
  it('重建 store 時從 localStorage 還原上次選擇', () => {
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    localStorage.setItem(BACKGROUND_STORAGE_KEY, target)
    // 重新建立 pinia 模擬 reload
    setActivePinia(createPinia())
    const s = useAppearanceStore()
    expect(s.current).toBe(target)
  })

  it('localStorage 存壞值時退回預設', () => {
    localStorage.setItem(BACKGROUND_STORAGE_KEY, 'garbage')
    setActivePinia(createPinia())
    const s = useAppearanceStore()
    expect(s.current).toBe(DEFAULT_BACKGROUND)
  })
})

describe('appearance store — 套用到根元素', () => {
  it('applyToDocument 把 current 寫到根 data-bg', () => {
    const s = useAppearanceStore()
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    s.setBackground(target)
    s.applyToDocument()
    expect(document.documentElement.getAttribute('data-bg')).toBe(target)
  })

  it('setBackground 後再 applyToDocument 反映最新選擇', () => {
    const s = useAppearanceStore()
    s.applyToDocument()
    expect(document.documentElement.getAttribute('data-bg')).toBe(DEFAULT_BACKGROUND)
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    s.setBackground(target)
    s.applyToDocument()
    expect(document.documentElement.getAttribute('data-bg')).toBe(target)
  })
})
