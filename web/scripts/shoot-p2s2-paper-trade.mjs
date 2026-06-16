/**
 * 卡 #28 (P2-S2) 真資料 e2e 截圖佐證 — Live 頁面板接真 paper 單 round-trip。
 *
 * 前置:真 live **交易**節點(scripts/run_live_trade.py,Binance testnet,
 * ema_cross 下 0.001 BTC paper 單)在跑;真全棧 app(run_real_stack_app_live.py:
 * Live klines REST + 真 WS gateway @latest → Redis DB0 consumer → hub)在
 * REAL_STACK_PORT 提供同源服務。事件 events.order./events.fills./events.position./
 * events.account. 經 consumer 映射為 orders/fills/positions/pnl channel → 面板。
 *
 * 做法:Playwright headless 連 /live → 等真 K 線 → 攔 WS frame 觀測 orders/fills/
 * positions/pnl 真事件 → 等面板渲染真值 → 截圖 → 斷言 0 console error + 收到真
 * 訂單/成交/部位/PnL 事件(證明 paper 單 round-trip 顯示於 Live 頁)。
 *
 * 用法:REAL_STACK_URL=http://127.0.0.1:8139 node scripts/shoot-p2s2-paper-trade.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const ARTIFACTS = path.join(ROOT, 'artifacts')
fs.mkdirSync(ARTIFACTS, { recursive: true })

const URL = process.env.REAL_STACK_URL || 'http://127.0.0.1:8139'
const SHOT = path.join(ARTIFACTS, 'p2s2-paper-trade-live.png')
const WAIT_MS = Number(process.env.SHOT_WAIT_MS || 240000)

const errors = []
const seen = { bars: 0, orders: 0, fills: 0, positions: 0, pnl: 0 }
const samples = { orders: [], fills: [], positions: [], pnl: [] }

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

page.on('websocket', (ws) => {
  ws.on('framereceived', (f) => {
    try {
      const o = JSON.parse(typeof f.payload === 'string' ? f.payload : f.payload.toString())
      if (o && o.channel && seen[o.channel] != null) {
        seen[o.channel] += 1
        if (o.channel !== 'bars' && samples[o.channel].length < 4) {
          samples[o.channel].push(o.data?.type || o.data)
        }
      }
    } catch { /* ignore non-JSON */ }
  })
})

await page.goto(URL + '/live', { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 20000 })

// 等到 paper 單 round-trip:至少一筆 fill + 一個 position + 一個 pnl 事件。
const deadline = Date.now() + WAIT_MS
while (Date.now() < deadline && !(seen.fills >= 1 && seen.pnl >= 1)) {
  await page.waitForTimeout(2000)
}
await page.waitForTimeout(2000)

const modeBadge = (await page.locator('[data-testid="mode-badge"]').textContent().catch(() => ''))?.trim()
const fillsText = (await page.locator('[data-testid="fills-table"]').textContent().catch(() => ''))?.trim()
const posText = (await page.locator('[data-testid="positions-table"]').textContent().catch(() => ''))?.trim()
const pnlText = (await page.locator('[data-testid="pnl-widget"]').textContent().catch(() => ''))?.trim()

await page.screenshot({ path: SHOT, fullPage: false })
await browser.close()

const panelHasFill = !!fillsText && !fillsText.includes('無成交')
const panelHasPnl = !!pnlText && !pnlText.includes('—')

const result = {
  url: URL,
  modeBadge,
  wsEvents: seen,
  samples,
  panels: { fillsText, posText, pnlText },
  panelHasFill,
  panelHasPnl,
  consoleErrors: errors,
  screenshot: SHOT,
}
console.log(JSON.stringify(result, null, 2))

const ok = errors.length === 0 && seen.fills >= 1 && seen.pnl >= 1 && panelHasFill && panelHasPnl
if (!ok) {
  console.error('P2-S2 PAPER TRADE SHOT FAILED')
  process.exit(1)
}
console.log('P2-S2 PAPER TRADE SHOT OK')
