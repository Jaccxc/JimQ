/**
 * 卡 #30 (P2-S1b) 真資料 e2e 截圖佐證(非 mock)。
 *
 * 前置:真 live 節點(run_live_data.py,Binance testnet,訂 BTCUSDT-PERP)在跑,
 * #30 真全棧 app(scripts/run_real_stack_app_live.py:真 /api/v1/live/bars 近期真
 * klines + 真 WS gateway @latest → Redis DB0 consumer → hub)在 REAL_STACK_PORT
 * 提供同源服務。
 *
 * 驗收(卡 #30):
 * - Live 頁初始載入用近期真 klines(攔 /api/v1/live/bars 回應,價位在 ~66k 真 BTC
 *   區間,非 2024 catalog 的 ~40k)。
 * - live WS bar → 蠟燭逐根更新/append(收到真 live bar,價位與初始 history 連貫,
 *   同區間無斷裂)。
 * - 截圖 + 0 console error + chart canvas 存在。
 *
 * 用法:REAL_STACK_URL=http://127.0.0.1:8138 node scripts/shoot-live-candles.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const ARTIFACTS = path.join(ROOT, 'artifacts')
fs.mkdirSync(ARTIFACTS, { recursive: true })

const URL = process.env.REAL_STACK_URL || 'http://127.0.0.1:8138'
const SHOT = path.join(ARTIFACTS, 'p2s1b-live-candles.png')

const errors = []
const wsBars = [] // 真 WS 推來的 bar close。
let historyPrices = [] // 初始載入 /api/v1/live/bars 的 close（近期真 klines）。
let liveBarsEndpointHit = false

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

// 攔 /api/v1/live/bars 回應:證明初始載入走近期真 klines(非 2024 catalog /bars)。
page.on('response', async (resp) => {
  try {
    const u = resp.url()
    if (u.includes('/api/v1/live/bars')) {
      liveBarsEndpointHit = true
      const body = await resp.json()
      if (Array.isArray(body)) historyPrices = body.map((b) => Number(b.close)).filter(Number.isFinite)
    }
  } catch { /* ignore */ }
})

// 攔 WS frame，觀測真 live bar close(證明逐根更新到前端)。
page.on('websocket', (ws) => {
  ws.on('framereceived', (f) => {
    try {
      const o = JSON.parse(typeof f.payload === 'string' ? f.payload : f.payload.toString())
      if (o && o.channel === 'bars' && o.data && o.data.close) wsBars.push(Number(o.data.close))
    } catch { /* ignore */ }
  })
})

await page.goto(URL + '/live', { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 20000 })

// 等到收到真 live bar(逐根更新)。
await page.waitForTimeout(2000)
const deadline = Date.now() + 90000
while (Date.now() < deadline && wsBars.length < 2) {
  await page.waitForTimeout(1000)
}
await page.waitForTimeout(1500)

const modeBadge = (await page.locator('[data-testid="mode-badge"]').textContent().catch(() => ''))?.trim()
const connStatus = await page.locator('[data-testid="conn-status"]').getAttribute('data-status').catch(() => null)
const canvasCount = await page.locator('[data-testid="candle-chart"] canvas').count()

await page.screenshot({ path: SHOT, fullPage: false })
await browser.close()

const liveP = wsBars.filter(Number.isFinite)
const histMin = historyPrices.length ? Math.min(...historyPrices) : null
const histMax = historyPrices.length ? Math.max(...historyPrices) : null
const liveMin = liveP.length ? Math.min(...liveP) : null
const liveMax = liveP.length ? Math.max(...liveP) : null

// 真 Binance testnet BTC 在數萬美元級(~66k),遠離 2024 catalog 的 ~40k。
const inBtcBand = (n) => n != null && n > 50000 && n < 200000
// 連貫性:初始 history 與 live bar 都在真 BTC 區間,且彼此接近(同 venue,< 10% 落差)。
const histInBand = historyPrices.length > 100 && inBtcBand(histMin) && inBtcBand(histMax)
const liveInBand = liveP.length >= 1 && inBtcBand(liveMin) && inBtcBand(liveMax)
const continuous =
  histInBand && liveInBand &&
  Math.abs((liveMin + liveMax) / 2 - (histMin + histMax) / 2) / ((histMin + histMax) / 2) < 0.1

const result = {
  url: URL,
  modeBadge,
  connStatus,
  canvasCount,
  liveBarsEndpointHit,
  historyCount: historyPrices.length,
  historyPriceRange: [histMin, histMax],
  wsLiveBarCount: liveP.length,
  liveBarPriceRange: [liveMin, liveMax],
  sampleLivePrices: liveP.slice(0, 6),
  continuous,
  consoleErrors: errors,
  screenshot: SHOT,
}
console.log(JSON.stringify(result, null, 2))

if (errors.length || canvasCount < 1 || !liveBarsEndpointHit || !histInBand || !liveInBand || !continuous) {
  console.error('LIVE CANDLES SHOT FAILED')
  process.exit(1)
}
console.log('LIVE CANDLES SHOT OK')
