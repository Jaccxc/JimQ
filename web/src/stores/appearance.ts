/**
 * 外觀 store:app 背景設計選擇器 + persist + 套用到根元素。
 *
 * 緣由(改版):玻璃面板(GlassPanel L1)的 blur/折射/高光,需要底層背景「有層次/有色彩」
 * 才會顯現;原本單一純色 --bg 讓玻璃「糊」在背景上。本 store 管理 5 種深色背景設計,
 * 使用者可從 header 的外觀選擇器即時切換,選擇 persist 到 localStorage,reload 維持。
 *
 * 套用機制:把 current id 寫到 document 根元素的 data-bg attribute;實際背景樣式集中在
 * web/src/styles/backgrounds.css(以 [data-bg="..."] 選擇器命中),沿用 theme.css token。
 *
 * 設計原則(契約):大面積背景禁 backdrop-filter;動畫只用 transform/opacity 且尊重
 * prefers-reduced-motion;每種背景上玻璃面板文字對比 ≥ 4.5:1。
 */
import { defineStore } from 'pinia'

export interface BackgroundOption {
  /** data-bg 值 / localStorage 值。 */
  id: string
  /** UI 顯示標籤。 */
  label: string
  /** 一句話描述,供選擇器副標。 */
  description: string
  /** 縮圖預覽用色票(CSS 漸層字串),選擇器小卡顯示。 */
  swatch: string
}

/** localStorage key(穩定契約,勿改;改了會讓既有使用者偏好失效)。 */
export const BACKGROUND_STORAGE_KEY = 'jimq.appearance.background'

/**
 * 5 種背景設計(深色基底、Apple 質感、讓玻璃顯現)。
 * id 對應 backgrounds.css 的 [data-bg="id"] 選擇器。
 */
export const BACKGROUNDS: BackgroundOption[] = [
  {
    id: 'aurora',
    label: 'Aurora Mesh',
    description: '多色團柔和融合,Apple 桌布感',
    swatch:
      'radial-gradient(60% 80% at 25% 20%, #1d4ed8 0%, transparent 60%), radial-gradient(60% 80% at 80% 30%, #7c3aed 0%, transparent 60%), radial-gradient(70% 90% at 60% 100%, #0e7490 0%, transparent 60%), #0b0e14',
  },
  {
    id: 'orbs',
    label: 'Ambient Orbs',
    description: '發光色球緩慢飄移,折射最明顯',
    swatch:
      'radial-gradient(35% 40% at 20% 30%, #2563eb 0%, transparent 70%), radial-gradient(30% 35% at 78% 65%, #9333ea 0%, transparent 70%), radial-gradient(28% 30% at 55% 15%, #0891b2 0%, transparent 70%), #0a0d13',
  },
  {
    id: 'grain',
    label: 'Mesh + Grain',
    description: '對角漸層 + 細噪點 + vignette',
    swatch:
      'linear-gradient(135deg, #16213a 0%, #0b0e14 45%, #1a1230 100%)',
  },
  {
    id: 'grid',
    label: 'Grid Glow',
    description: '深底 + 極淡格線 + 局部光暈(科技感)',
    swatch:
      'radial-gradient(60% 60% at 50% 0%, rgba(10,132,255,0.35) 0%, transparent 60%), #090c12',
  },
  {
    id: 'minimal',
    label: 'Deep Gradient',
    description: '單一方向深色漸層 + 頂部微光(最克制)',
    swatch:
      'linear-gradient(180deg, #141a26 0%, #0b0e14 60%, #080a0f 100%)',
  },
]

/** 預設挑最能展示玻璃的(Aurora)。 */
export const DEFAULT_BACKGROUND = 'aurora'

function isValidBackground(id: unknown): id is string {
  return typeof id === 'string' && BACKGROUNDS.some((b) => b.id === id)
}

/** 從 localStorage 還原;壞值/缺值退回預設。SSR/無 window 防護。 */
function restore(): string {
  if (typeof localStorage === 'undefined') return DEFAULT_BACKGROUND
  const saved = localStorage.getItem(BACKGROUND_STORAGE_KEY)
  return isValidBackground(saved) ? saved : DEFAULT_BACKGROUND
}

interface State {
  current: string
}

export const useAppearanceStore = defineStore('appearance', {
  state: (): State => ({
    current: restore(),
  }),
  getters: {
    /** 目前背景的完整選項(label/description/swatch)。 */
    currentOption(state): BackgroundOption {
      return (
        BACKGROUNDS.find((b) => b.id === state.current) ??
        BACKGROUNDS.find((b) => b.id === DEFAULT_BACKGROUND)!
      )
    },
  },
  actions: {
    /** 選擇背景:更新 current、persist、即時套用到根元素。不合法 id 忽略。 */
    setBackground(id: string) {
      if (!isValidBackground(id)) return
      this.current = id
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(BACKGROUND_STORAGE_KEY, id)
      }
      this.applyToDocument()
    },
    /** 把 current 寫到 document 根元素 data-bg(背景樣式由 backgrounds.css 命中)。 */
    applyToDocument() {
      if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-bg', this.current)
      }
    },
  },
})
