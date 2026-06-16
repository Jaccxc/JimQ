/**
 * 改版 S1b — 玻璃 primitives 行為冒煙測試(透過 public interface)。
 * StatPill 依 value 反映方向 + tone;GlassPanel/GlassToolbar 落正確 glass class。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatPill from '@/components/ui/glass/StatPill.vue'
import GlassPanel from '@/components/ui/glass/GlassPanel.vue'
import GlassToolbar from '@/components/ui/glass/GlassToolbar.vue'
import { Badge } from '@/components/ui/badge'

describe('StatPill', () => {
  it('正值 → data-direction=up 且套漲色', () => {
    const w = mount(StatPill, { props: { value: 12.5 } })
    expect(w.attributes('data-direction')).toBe('up')
    expect(w.classes().join(' ')).toContain('--color-up')
  })

  it('負值 → data-direction=down 且套跌色', () => {
    const w = mount(StatPill, { props: { value: -3 } })
    expect(w.attributes('data-direction')).toBe('down')
    expect(w.classes().join(' ')).toContain('--color-down')
  })

  it('0 → data-direction=flat', () => {
    const w = mount(StatPill, { props: { value: 0 } })
    expect(w.attributes('data-direction')).toBe('flat')
  })

  it('signed 正值加 + 前綴;formatted 覆寫顯示', () => {
    expect(mount(StatPill, { props: { value: 5, signed: true } }).text()).toBe('+5')
    expect(
      mount(StatPill, { props: { value: -3, formatted: '-3.00' } }).text(),
    ).toBe('-3.00')
  })
})

describe('Glass primitives', () => {
  it('GlassPanel 預設落 glass-l1 + section', () => {
    const w = mount(GlassPanel, { slots: { default: 'x' } })
    expect(w.classes()).toContain('glass-l1')
    expect(w.element.tagName.toLowerCase()).toBe('section')
  })

  it('GlassToolbar 落 glass-l3', () => {
    const w = mount(GlassToolbar, { slots: { default: 'x' } })
    expect(w.classes()).toContain('glass-l3')
  })

  it('Badge up 變體吃 up-pill token', () => {
    const w = mount(Badge, { props: { variant: 'up' }, slots: { default: '+1%' } })
    expect(w.classes().join(' ')).toContain('--color-up')
  })
})
