/**
 * 卡 #22 (W3) headless 視覺佐證:標的/週期切換 + EMA 疊圖。
 *
 * 不需真後端:
 *  1) 靜態伺服 dist/。
 *  2) mock REST /api/v1/bars → 依 symbol/timeframe 回不同價位的 BarDTO[]
 *     (BTC ~40000、ETH ~2200;1m vs 5m 不同 bar 間距),驗證「切換重載歷史」。
 *  3) mock WS /ws/stream → 推近幾根 snapshot bars + {type:live}(連線穩定佐證)。
 *  4) Playwright 載入 → 截圖:初始 → 開 EMA fast+slow → 切換到 ETHUSDT-PERP →
 *     切換週期到 5m。每步等 canvas 重畫,console error 即失敗。
 *
 * 重點驗收:切換後不出現重複 series(controller.reset 重用 chart)、無 console error。
 */
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { WebSocketServer } from 'ws'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const DIST = path.join(ROOT, 'dist')
const ARTIFACTS = path.join(ROOT, 'artifacts')
fs.mkdirSync(ARTIFACTS, { recursive: true })

const PORT = 4322
const NS = 1_000_000_000
const T0 = 1_700_000_000

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' }

// 依 symbol/timeframe 產生有辨識度的歷史 bars(不同基準價 + 不同間距)。
function basePrice(symbol) {
  return symbol.startsWith('ETH') ? 2200 : 40000
}
function stepSec(timeframe) {
  return timeframe === '5m' ? 300 : 60
}
function makeBars(symbol, timeframe, n = 120) {
  const base = basePrice(symbol)
  const step = stepSec(timeframe)
  const amp = base * 0.01
  const out = []
  let px = base
  for (let i = 0; i < n; i++) {
    const time = T0 + i * step
    const open = px
    const close = base + Math.sin(i / 6) * amp + i * (base * 0.0003)
    const high = Math.max(open, close) + amp * 0.2
    const low = Math.min(open, close) - amp * 0.2
    px = close
    out.push({
      ts: time * NS, time,
      open: open.toFixed(2), high: high.toFixed(2), low: low.toFixed(2),
      close: close.toFixed(2), volume: '10.0',
    })
  }
  return out
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)
  if (url.pathname === '/api/v1/bars') {
    const symbol = url.searchParams.get('symbol') || 'BTCUSDT-PERP.BINANCE'
    const timeframe = url.searchParams.get('timeframe') || '1m'
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify(makeBars(symbol, timeframe)))
    return
  }
  let p = url.pathname === '/' ? '/index.html' : url.pathname
  let fp = path.join(DIST, p)
  if (!fs.existsSync(fp)) fp = path.join(DIST, 'index.html')
  const ext = path.extname(fp)
  fs.readFile(fp, (err, buf) => {
    if (err) { res.writeHead(404); res.end('not found'); return }
    res.writeHead(200, { 'content-type': MIME[ext] ?? 'application/octet-stream' })
    res.end(buf)
  })
})

const wss = new WebSocketServer({ server, path: '/ws/stream' })
wss.on('connection', (ws) => {
  let seq = 0
  const send = (o) => ws.readyState === ws.OPEN && ws.send(JSON.stringify(o))
  // 推一小段 BTC snapshot 後 live(僅佐證連線穩定;歷史以 REST 為主)。
  for (const b of makeBars('BTCUSDT-PERP.BINANCE', '1m', 3)) {
    send({ channel: 'bars', seq: ++seq, data: { type: 'Bar', ...b }, snapshot: true })
  }
  send({ type: 'live' })
})

const errors = []
await new Promise((r) => server.listen(PORT, r))
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 15000 })
await page.waitForTimeout(1200)

const shots = {}
async function shoot(name) {
  const fp = path.join(ARTIFACTS, `w3-${name}.png`)
  await page.screenshot({ path: fp, fullPage: false })
  shots[name] = fp
}

// 0) 初始 BTC 1m。
await shoot('01-initial-btc-1m')

// 1) 開啟 EMA fast + slow。
await page.locator('[data-testid="ema-fast-toggle"]').check()
await page.locator('[data-testid="ema-slow-toggle"]').check()
await page.waitForTimeout(600)
await shoot('02-ema-overlay')

// canvas 數量(切換前)。
const canvasBefore = await page.locator('[data-testid="candle-chart"] canvas').count()

// 2) 切換標的 → ETHUSDT-PERP(EMA 維持開啟,驗證 reset 後重畫不重複 series)。
await page.locator('[data-testid="symbol-select"]').selectOption('ETHUSDT-PERP.BINANCE')
await page.waitForTimeout(900)
await shoot('03-switch-eth-1m')
const headerEth = await page.locator('.topbar h1').textContent()

// 3) 切換週期 → 5m。
await page.locator('[data-testid="timeframe-select"]').selectOption('5m')
await page.waitForTimeout(900)
await shoot('04-switch-eth-5m')
const headerEth5m = await page.locator('.topbar h1').textContent()

// canvas 數量(多次切換後)— 應與切換前相同(無重複 series 累積)。
const canvasAfter = await page.locator('[data-testid="candle-chart"] canvas').count()

const status = await page.locator('[data-testid="conn-status"]').getAttribute('data-status')

await browser.close()
server.close()
wss.close()

const result = {
  shots,
  canvasBefore,
  canvasAfter,
  canvasStable: canvasBefore === canvasAfter,
  headerEth: headerEth?.trim(),
  headerEth5m: headerEth5m?.trim(),
  connStatus: status,
  consoleErrors: errors,
}
console.log(JSON.stringify(result, null, 2))
const ok =
  errors.length === 0 &&
  canvasBefore >= 1 &&
  result.canvasStable &&
  /ETHUSDT-PERP/.test(result.headerEth || '') &&
  /5m/.test(result.headerEth5m || '')
if (!ok) { console.error('W3 VERIFY FAILED'); process.exit(1) }
console.log('W3 VERIFY OK')
