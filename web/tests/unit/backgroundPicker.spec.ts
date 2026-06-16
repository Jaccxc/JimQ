/**
 * 行為測試:BackgroundPicker(header 外觀/背景選擇器)。
 *
 * 驗 public 行為(不驗 reka-ui 內部):
 * - 開啟後列出全部 5 種背景選項。
 * - 點某選項 → appearance store 的 current 切到該 id(套用)。
 * - 切換後 persist(localStorage)且根元素 data-bg 更新。
 *
 * popover content 經 reka-ui portal 進 document.body,故 attachTo body 並查 document。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import BackgroundPicker from '@/components/controls/BackgroundPicker.vue'
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
afterEach(() => {
  document.body.innerHTML = ''
})

async function openPicker() {
  const w = mount(BackgroundPicker, { attachTo: document.body })
  await w.get('[data-testid="bg-picker-trigger"]').trigger('click')
  await new Promise((r) => setTimeout(r, 0))
  return w
}

describe('BackgroundPicker', () => {
  it('開啟後列出 5 種背景選項', async () => {
    await openPicker()
    for (const opt of BACKGROUNDS) {
      const el = document.querySelector(`[data-testid="bg-option-${opt.id}"]`)
      expect(el, `選項 ${opt.id} 應該存在`).not.toBeNull()
    }
  })

  it('點選某背景 → store current 切換到該 id', async () => {
    await openPicker()
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    const btn = document.querySelector(
      `[data-testid="bg-option-${target}"]`,
    ) as HTMLButtonElement
    btn.click()
    await new Promise((r) => setTimeout(r, 0))
    expect(useAppearanceStore().current).toBe(target)
  })

  it('點選後 persist 且根元素 data-bg 更新', async () => {
    await openPicker()
    const target = BACKGROUNDS.find((b) => b.id !== DEFAULT_BACKGROUND)!.id
    const btn = document.querySelector(
      `[data-testid="bg-option-${target}"]`,
    ) as HTMLButtonElement
    btn.click()
    await new Promise((r) => setTimeout(r, 0))
    expect(localStorage.getItem(BACKGROUND_STORAGE_KEY)).toBe(target)
    expect(document.documentElement.getAttribute('data-bg')).toBe(target)
  })
})
