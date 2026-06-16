/**
 * 卡 D — 行為測試:深色背景(#0e1117)下文字必須可見(非黑色)。
 *
 * 問題:RunExplorerView 的 <h2>(「Backtest Runs」「Run #73 · …」)與表格 th/td
 * 未設文字色 → 繼承瀏覽器預設黑色 → 在深色 body 上隱形(黑底黑字)。
 *
 * 修復策略:在 App.vue 全域 dark theme 補 base text + h1/h2 的淺色,讓所有未顯式
 * 設色的文字(含 RunExplorerView 的標題/表格)都繼承到可見的淺色。
 *
 * 本測試直接解析 SFC 的 <style> 來源,斷言全域有「非黑」文字色規則 —— 驗的是
 * 「使用者看得到字」這個行為的根因(jsdom 不套用 SFC 樣式,無法用 computedStyle
 * 直接量,故以樣式契約驗證)。
 */
import { describe, it, expect } from 'vitest'
// 以 Vite ?raw 取得 SFC 原始碼(含 <style>),驗全域 dark theme 文字色契約。
import appSource from '@/App.vue?raw'

/** 從 CSS 文字抓某 selector 區塊內 color 宣告值(取最後一個全域 <style> 內出現)。 */
function colorOf(css: string, selector: string): string | null {
  // 比對形如 `body { ... color: #abc; ... }` 的區塊。
  const re = new RegExp(
    `(?:^|[},])\\s*${selector.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`,
    'm',
  )
  const block = css.match(re)?.[1]
  if (!block) return null
  const m = block.match(/color\s*:\s*([^;]+);/)
  return m ? m[1].trim().toLowerCase() : null
}

/** 判斷顏色是否「非黑」(可見於深色背景)。黑 = #000 / #000000 / black / rgb(0,0,0)。 */
function isVisibleOnDark(color: string | null): boolean {
  if (!color) return false
  const c = color.replace(/\s+/g, '')
  const black = ['#000', '#000000', 'black', 'rgb(0,0,0)', 'rgba(0,0,0,1)']
  return !black.includes(c)
}

describe('dark theme 文字可見性', () => {
  const appCss = appSource

  it('App.vue 全域為 body 設淺色 base text(非黑)', () => {
    const c = colorOf(appCss, 'body')
    expect(isVisibleOnDark(c)).toBe(true)
  })

  it('App.vue 全域為 h1 設可見文字色(非黑)', () => {
    expect(isVisibleOnDark(colorOf(appCss, 'h1'))).toBe(true)
  })

  it('App.vue 全域為 h2 設可見文字色(非黑)', () => {
    expect(isVisibleOnDark(colorOf(appCss, 'h2'))).toBe(true)
  })

  it('RunExplorerView 的標題/表格不再依賴黑色預設:全域 base 已覆蓋', () => {
    // RunExplorerView 的 h2/th/td 不顯式設色,靠全域繼承;確保全域 body 與 h2 皆非黑。
    expect(isVisibleOnDark(colorOf(appCss, 'body'))).toBe(true)
    expect(isVisibleOnDark(colorOf(appCss, 'h2'))).toBe(true)
  })
})
