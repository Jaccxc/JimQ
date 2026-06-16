/**
 * 卡 #27 (P2-S1) headless 視覺佐證:tabbed shell + Live 頁顯示即時資料。
 *
 * 不需真後端(mock REST + WS 模擬 live 串流脊椎輸出):
 *  1) 靜態伺服 dist/。
 *  2) mock REST /api/v1/bars → BTCUSDT-PERP 1m BarDTO[](初始歷史 K 線)。
 *  3) mock WS /ws/stream → 推 snapshot bars + {type:live}(模擬 live 資料節點
 *     → Redis Streams → consumer → WS 的串流脊椎輸出;Live 頁據此顯示即時資料)。
 *  4) Playwright:載入 /live → 驗 mode badge = LIVE-TESTNET + chart 畫出 →
 *     切到 Backtest(badge=BACKTEST)→ Research(佔位)→ 回 Live。每步截圖,
 *     console error 即失敗。
 *
 * 驗收:Live 頁顯示資料 + tabbed 切換 + mode badge 正確 + 0 console error。
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

const PORT = 4323
const NS = 1_000_000_000
const T0 = 1_700_000_000

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' }

function makeBars(n = 120) {
  const base = 40000
  const amp = base * 0.01
  const out = []
  let px = base
  for (let i = 0; i < n; i++) {
    const time = T0 + i * 60
    const open = px
    const close = base + Math.sin(i / 6) * amp + i * (base * 0.0003)
    const high = Math.max(open, close) + amp * 0.2
    const low = Math.min(open, close) - amp * 0.2
    px = close
    out.push({
      ts: time * NS, time,
      open: open.toFixed(1), high: high.toFixed(1), low: low.toFixed(1),
      close: close.toFixed(1), volume: '10.0',
    })
  }
  return out
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)
  if (url.pathname === '/api/v1/bars') {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify(makeBars()))
    return
  }
  // 其它 REST(backtests/trades 等)回空,避免視圖 onMounted 噴錯。
  if (url.pathname.startsWith('/api/')) {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end('[]')
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
// 全域單調游標:跨多次連線(切分頁會重連)live bar 時間永遠遞增,確保嚴格新於
// REST 歷史尾端(T0+119*60),避免 lightweight-charts 拒絕亂序更新(模擬真實
// 單一單調串流)。從 200 起遠離歷史尾端。
let liveCursor = 200
let liveSeq = 0
wss.on('connection', (ws) => {
  const send = (o) => ws.readyState === ws.OPEN && ws.send(JSON.stringify(o))
  send({ type: 'live' })
  const t = setInterval(() => {
    const time = T0 + liveCursor * 60
    const close = 41000 + Math.sin(liveCursor / 6) * 300
    send({ channel: 'bars', seq: ++liveSeq, data: { type: 'Bar', ts: time * NS, time, open: close.toFixed(1), high: (close + 30).toFixed(1), low: (close - 30).toFixed(1), close: close.toFixed(1), volume: '5.0' } })
    liveCursor++
  }, 400)
  ws.on('close', () => clearInterval(t))
})

const errors = []
await new Promise((r) => server.listen(PORT, r))
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

const shots = {}
async function shoot(name) {
  const fp = path.join(ARTIFACTS, `p2s1-${name}.png`)
  await page.screenshot({ path: fp, fullPage: false })
  shots[name] = fp
}

// 1) Live 頁:badge LIVE-TESTNET + chart 顯示即時資料。
await page.goto(`http://localhost:${PORT}/live`, { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 15000 })
await page.waitForTimeout(1500)
const liveBadge = (await page.locator('[data-testid="mode-badge"]').textContent())?.trim()
await shoot('01-live')

// 2) 切到 Backtest 分頁 → badge BACKTEST。
await page.locator('nav.tabs a', { hasText: 'Backtest' }).click()
await page.waitForTimeout(1200)
const backtestBadge = (await page.locator('[data-testid="mode-badge"]').textContent())?.trim()
await shoot('02-backtest')

// 3) 切到 Research 分頁 → 佔位。
await page.locator('nav.tabs a', { hasText: 'Research' }).click()
await page.waitForTimeout(500)
const researchVisible = await page.locator('[data-testid="research-placeholder"]').isVisible()
await shoot('03-research')

// 4) 回 Live → badge 再次 LIVE-TESTNET。
await page.locator('nav.tabs a', { hasText: 'Live' }).click()
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 15000 })
await page.waitForTimeout(1200)
const liveBadge2 = (await page.locator('[data-testid="mode-badge"]').textContent())?.trim()
const connStatus = await page.locator('[data-testid="conn-status"]').getAttribute('data-status')
const killDisabled = await page.locator('[data-testid="kill-switch"]').isDisabled()
await shoot('04-back-to-live')

await browser.close()
server.close()
wss.close()

const result = {
  shots,
  liveBadge,
  backtestBadge,
  researchVisible,
  liveBadge2,
  connStatus,
  killDisabled,
  consoleErrors: errors,
}
console.log(JSON.stringify(result, null, 2))
const ok =
  errors.length === 0 &&
  liveBadge === 'LIVE-TESTNET' &&
  backtestBadge === 'BACKTEST' &&
  researchVisible === true &&
  liveBadge2 === 'LIVE-TESTNET' &&
  killDisabled === true
if (!ok) { console.error('P2S1 VERIFY FAILED'); process.exit(1) }
console.log('P2S1 VERIFY OK')
