// 一次性截圖佐證:回放開頭預設窗(~70 根非 2 根)、進出場 marker 不同價 + 乾淨格式。
// 用法:node scripts/shot-replay-fixes.mjs  (需 web 在 http://localhost:8080)
import { chromium } from 'playwright'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ART = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'artifacts')
const BASE = process.env.BASE_URL ?? 'http://localhost:8080'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

await page.goto(`${BASE}/backtest`, { waitUntil: 'networkidle' })
// 等 run history 列表出現,選 run #94。
await page.waitForSelector('[data-testid="run-row-94"]', { timeout: 15000 })
await page.click('[data-testid="run-row-94"]')

// 回放開頭:剛 load,只有 1~2 根 bar → 應為 ~70 根寬窗(非 2 根超大蠟燭)。
await page.waitForSelector('[data-testid="replay-chart"]', { timeout: 10000 })
await page.waitForTimeout(600)
await page.screenshot({ path: path.join(ART, 'replay-start-70bar-window.png') })

// 暫停(若有播放),讓畫面停住便於看 marker。
const pauseBtn = page.locator('button[aria-label="暫停"], button[title*="暫停"]')
if (await pauseBtn.count()) await pauseBtn.first().click().catch(() => {})

// 跳到結尾顯示完整段:進出場 marker 全出來,可檢視格式與不同價。
const toEnd = page.locator('button[aria-label*="結尾"], button[title*="結尾"], button:has-text("⏭")')
if (await toEnd.count()) {
  await toEnd.first().click().catch(() => {})
  await page.waitForTimeout(800)
}
await page.screenshot({ path: path.join(ART, 'replay-end-markers-full.png') })

// 放大檢視 marker 文字:hover 一個 marker 區域並截一張(整圖,marker 文字浮現)。
await page.mouse.move(720, 420)
await page.waitForTimeout(300)
await page.screenshot({ path: path.join(ART, 'replay-marker-hover.png') })

await browser.close()
console.log('screenshots written to', ART)
