// 截圖佐證:放大到少量 bar,讓進出場 marker 的文字(去尾零格式)清晰可讀,
// 並驗進場(綠箭頭)與出場(amber 圈)在不同價位。
import { chromium } from 'playwright'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ART = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'artifacts')
const BASE = process.env.BASE_URL ?? 'http://localhost:8080'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } })
await page.goto(`${BASE}/backtest`, { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="run-row-94"]', { timeout: 15000 })
await page.click('[data-testid="run-row-94"]')
await page.waitForSelector('[data-testid="replay-chart"]', { timeout: 10000 })
await page.waitForTimeout(500)

// 暫停回放。
const pauseBtn = page.locator('button[title*="暫停"], button[aria-label*="暫停"]')
if (await pauseBtn.count()) await pauseBtn.first().click().catch(() => {})

// scrub 進度條到 ~15%(少量 bar,marker 間距大、文字可讀)。
const scrub = page.locator('input[type="range"]').first()
if (await scrub.count()) {
  const box = await scrub.boundingBox()
  if (box) {
    await page.mouse.click(box.x + box.width * 0.12, box.y + box.height / 2)
    await page.waitForTimeout(600)
  }
}

// 對圖區滾輪放大,讓 bar 間距更大(LWC 滾輪縮放)。
const chart = page.locator('[data-testid="replay-chart"]')
const cbox = await chart.boundingBox()
if (cbox) {
  const cx = cbox.x + cbox.width * 0.6
  const cy = cbox.y + cbox.height * 0.4
  for (let i = 0; i < 6; i++) {
    await page.mouse.move(cx, cy)
    await page.mouse.wheel(0, -120)
    await page.waitForTimeout(120)
  }
}
await page.waitForTimeout(400)
await page.screenshot({ path: path.join(ART, 'replay-marker-zoom-readable.png') })

await browser.close()
console.log('done')
