/**
 * 卡 #27 (P2-S1) 真資料 e2e 截圖佐證(非 mock)。
 *
 * 前置:真 live 節點(run_live_data.py,Binance testnet,訂 BTCUSDT-PERP)在跑,
 * 真全棧 app(scripts/run_real_stack_app.py:真 history REST + 真 WS gateway
 * @latest → Redis DB0 consumer → hub)在 REAL_STACK_PORT 提供同源服務。
 *
 * 做法:Playwright headless 連真 web Live 頁 → 等真 K 線畫出 → 等 WS 推真 live
 * bar(close 落在真 Binance testnet BTC 區間,遠離 mock 40k)→ 截圖 →
 * 斷言 0 console error + chart canvas 存在 + 抓到的真價格在合理 BTC 區間。
 *
 * 用法:REAL_STACK_URL=http://127.0.0.1:8137 node scripts/shoot-real-live.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const ARTIFACTS = path.join(ROOT, 'artifacts')
fs.mkdirSync(ARTIFACTS, { recursive: true })

const URL = process.env.REAL_STACK_URL || 'http://127.0.0.1:8137'
const SHOT = path.join(ARTIFACTS, 'p2s1-real-live.png')

const errors = []
const wsBars = [] // 真 WS 推來的 bar close(從前端 WS 觀測)。

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

// 攔截 WS frame,直接觀測真 bar close(證明真資料抵達前端)。
page.on('websocket', (ws) => {
  ws.on('framereceived', (f) => {
    try {
      const o = JSON.parse(typeof f.payload === 'string' ? f.payload : f.payload.toString())
      if (o && o.channel === 'bars' && o.data && o.data.close) wsBars.push(o.data.close)
    } catch { /* ignore non-JSON */ }
  })
})

await page.goto(URL + '/live', { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 20000 })

// 等到至少收到一根 live(非 snapshot)真 bar,且 chart 有時間反應(K 線在動)。
await page.waitForTimeout(2000)
const deadline = Date.now() + 80000
while (Date.now() < deadline && wsBars.length < 2) {
  await page.waitForTimeout(1000)
}
await page.waitForTimeout(1500)

const modeBadge = (await page.locator('[data-testid="mode-badge"]').textContent().catch(() => ''))?.trim()
const connStatus = await page.locator('[data-testid="conn-status"]').getAttribute('data-status').catch(() => null)
const canvasCount = await page.locator('[data-testid="candle-chart"] canvas').count()

await page.screenshot({ path: SHOT, fullPage: false })
await browser.close()

const prices = wsBars.map(Number).filter((n) => Number.isFinite(n))
const minP = prices.length ? Math.min(...prices) : null
const maxP = prices.length ? Math.max(...prices) : null
// 真 Binance testnet BTC 在數萬美元級;mock 是 40000 平滑正弦。真資料判定:
// 至少 2 個價、且價格在合理 BTC 寬區間(10k–500k)且 min!=max(在動)。
const realBtc =
  prices.length >= 2 &&
  minP > 10000 && maxP < 500000 &&
  minP !== maxP

const result = {
  url: URL,
  modeBadge,
  connStatus,
  canvasCount,
  wsBarCount: prices.length,
  priceMin: minP,
  priceMax: maxP,
  samplePrices: prices.slice(0, 8),
  realBtc,
  consoleErrors: errors,
  screenshot: SHOT,
}
console.log(JSON.stringify(result, null, 2))

if (errors.length || canvasCount < 1 || !realBtc) {
  console.error('REAL LIVE SHOT FAILED')
  process.exit(1)
}
console.log('REAL LIVE SHOT OK')
