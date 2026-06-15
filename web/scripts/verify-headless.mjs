/**
 * Headless 視覺佐證(best-effort,卡 #9)。
 *
 * 不需真後端:本腳本自帶
 *  1) 靜態伺服 dist/(vite build 產物)。
 *  2) mock REST /api/v1/bars → 回真形狀 BarDTO[]。
 *  3) mock WS /ws/stream → 推真信封流(補洞/快照 snapshot:true → {type:live}
 *     → delta:bars/orders(含 SL/TP bracket 子單)/fills/positions/pnl/heartbeat)。
 *  4) Playwright(home cache chromium)headless 載入 → 等 canvas 渲染 →
 *     截圖到 web/artifacts/ → console 有 error 即失敗。
 *
 * 信封形狀對齊 api/tests/test_nautilus_consumer.py 與 ws/stream.py。
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

const PORT = 4321
const NS = 1_000_000_000
const T0 = 1_700_000_000 // epoch 秒
const SYMBOL = 'BTCUSDT-PERP.BINANCE'

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' }

// --- mock 歷史 bars(REST)---
function makeBars(n, start) {
  const out = []
  let px = 40000
  for (let i = 0; i < n; i++) {
    const time = start + i * 60
    const open = px
    const close = px + (Math.sin(i / 5) * 40)
    const high = Math.max(open, close) + 15
    const low = Math.min(open, close) - 15
    px = close
    out.push({
      ts: time * NS, time,
      open: open.toFixed(1), high: high.toFixed(1), low: low.toFixed(1),
      close: close.toFixed(1), volume: '10.0',
    })
  }
  return out
}
const HISTORY = makeBars(120, T0)
const LAST = HISTORY[HISTORY.length - 1]

// --- HTTP server(靜態 + REST mock)---
const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)
  if (url.pathname === '/api/v1/bars') {
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify(HISTORY))
    return
  }
  let p = url.pathname === '/' ? '/index.html' : url.pathname
  let fp = path.join(DIST, p)
  if (!fs.existsSync(fp)) fp = path.join(DIST, 'index.html') // SPA fallback
  const ext = path.extname(fp)
  fs.readFile(fp, (err, buf) => {
    if (err) { res.writeHead(404); res.end('not found'); return }
    res.writeHead(200, { 'content-type': MIME[ext] ?? 'application/octet-stream' })
    res.end(buf)
  })
})

// --- WS server(/ws/stream)推真信封流 ---
const wss = new WebSocketServer({ server, path: '/ws/stream' })
wss.on('connection', (ws) => {
  let seq = 0
  const send = (o) => ws.readyState === ws.OPEN && ws.send(JSON.stringify(o))
  const env = (channel, data, extra = {}) => send({ channel, seq: ++seq, data, ...extra })

  // 1) 快照:近幾根 bars(snapshot:true)。
  for (const b of HISTORY.slice(-3)) env('bars', { type: 'Bar', ...b }, { snapshot: true })
  // 2) live 分界。
  send({ type: 'live' })

  // 3) delta replay:新 bar + 進場(order MARKET + SL/TP bracket)+ fill + position + pnl。
  let i = 1
  const tEntry = LAST.time + 5 * 60
  const timer = setInterval(() => {
    const time = LAST.time + i * 60
    const close = (Number(LAST.close) + Math.sin(i / 3) * 60).toFixed(1)
    env('bars', {
      type: 'Bar', ts: time * NS, time,
      open: LAST.close, high: (Number(close) + 20).toFixed(1),
      low: (Number(close) - 20).toFixed(1), close, volume: '12.0',
    })

    if (i === 5) {
      // 進場 MARKET BUY。
      env('orders', { type: 'OrderInitialized', instrument_id: SYMBOL, client_order_id: 'O-ENTRY', order_side: 'BUY', order_type: 'MARKET', quantity: '0.100', ts_init: String(tEntry * NS) })
      // bracket:SL STOP_MARKET + TP LIMIT。
      env('orders', { type: 'OrderInitialized', instrument_id: SYMBOL, client_order_id: 'O-SL', order_side: 'SELL', order_type: 'STOP_MARKET', quantity: '0.100', trigger_price: (Number(LAST.close) - 400).toFixed(1), ts_init: String(tEntry * NS) })
      env('orders', { type: 'OrderInitialized', instrument_id: SYMBOL, client_order_id: 'O-TP', order_side: 'SELL', order_type: 'LIMIT', quantity: '0.100', price: (Number(LAST.close) + 600).toFixed(1), ts_init: String(tEntry * NS) })
      // 成交。
      env('fills', { type: 'OrderFilled', instrument_id: SYMBOL, client_order_id: 'O-ENTRY', position_id: 'P-1', order_side: 'BUY', order_type: 'MARKET', last_qty: '0.100', last_px: LAST.close, ts_init: String(tEntry * NS) })
      // 部位。
      env('positions', { type: 'PositionOpened', instrument_id: SYMBOL, position_id: 'P-1', entry: 'BUY', side: 'LONG', signed_qty: 0.1, quantity: '0.100', last_px: LAST.close, avg_px_open: Number(LAST.close), ts_init: String(tEntry * NS) })
      // PnL。
      env('pnl', { type: 'AccountState', account_id: 'BINANCE-001', base_currency: 'USDT', balances: [{ total: '998500.50', locked: '0', free: '998500.50', currency: 'USDT' }], ts_init: String(tEntry * NS) })
    }
    i++
    if (i > 12) { clearInterval(timer); send({ type: 'heartbeat', ts: Date.now() / 1000 }) }
  }, 80)

  ws.on('close', () => clearInterval(timer))
})

// --- run ---
const errors = []
await new Promise((r) => server.listen(PORT, r))
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'networkidle' })
// 等 canvas(LWC 畫布)出現且面板就緒。
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 15000 })
await page.waitForTimeout(1500) // 讓 WS replay 進來。
// 等部位/PnL 出現(WS 串流生效佐證)。
await page.waitForFunction(() => {
  const txt = document.querySelector('[data-testid="pnl-widget"]')?.textContent || ''
  return /\d/.test(txt) && txt.indexOf('—') === -1
}, { timeout: 8000 }).catch(() => {})

const shot = path.join(ARTIFACTS, 'dashboard.png')
await page.screenshot({ path: shot, fullPage: false })

const canvasCount = await page.locator('[data-testid="candle-chart"] canvas').count()
const status = await page.locator('[data-testid="conn-status"]').getAttribute('data-status')
const pnlText = (await page.locator('[data-testid="pnl-widget"]').textContent())?.trim()
const posRows = await page.locator('[data-testid="positions-table"] tbody tr').count()

await browser.close()
server.close()
wss.close()

const result = { canvasCount, connStatus: status, pnlText, positionRows: posRows, consoleErrors: errors, screenshot: shot }
console.log(JSON.stringify(result, null, 2))
if (errors.length || canvasCount < 1) {
  console.error('VERIFY FAILED')
  process.exit(1)
}
console.log('VERIFY OK')
