/**
 * 卡 #10 — 對**真運行的全棧**(docker-compose:web→nginx→api→hub→真 backtest 事件)
 * Playwright headless 截圖,當交付證據(非 mock)。
 *
 * 前置:全棧已 up,engine demo job 已跑過(真 BTCUSDT-PERP 歷史灌入 catalog +
 * 串流 backtest 事件落地 Redis、API 已 @latest 解析並排空 backlog 到 hub)。
 *
 * 用法:WEB_URL=http://127.0.0.1:8080 node scripts/shoot-real-stack.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const ARTIFACTS = path.join(ROOT, 'artifacts')
fs.mkdirSync(ARTIFACTS, { recursive: true })

const URL = process.env.WEB_URL || 'http://127.0.0.1:8080'

const errors = []
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

await page.goto(URL + '/', { waitUntil: 'networkidle' })
// 等 LWC 畫布(真 REST 歷史畫出來)。
await page.waitForSelector('[data-testid="candle-chart"] canvas', { timeout: 20000 })
// 等 WS snapshot(真 position/pnl)到達。
await page.waitForFunction(() => {
  const txt = document.querySelector('[data-testid="pnl-widget"]')?.textContent || ''
  return /\d/.test(txt) && txt.indexOf('—') === -1
}, { timeout: 15000 }).catch(() => {})
await page.waitForTimeout(2000)

const shot = path.join(ARTIFACTS, 'real-e2e-dashboard.png')
await page.screenshot({ path: shot, fullPage: false })

const canvasCount = await page.locator('[data-testid="candle-chart"] canvas').count()
const connStatus = await page.locator('[data-testid="conn-status"]').getAttribute('data-status').catch(() => null)
const pnlText = (await page.locator('[data-testid="pnl-widget"]').textContent().catch(() => ''))?.trim()
const posRows = await page.locator('[data-testid="positions-table"] tbody tr').count().catch(() => 0)
const orderRows = await page.locator('[data-testid="orders-table"] tbody tr').count().catch(() => 0)

await browser.close()

const result = {
  url: URL,
  canvasCount,
  connStatus,
  pnlText,
  positionRows: posRows,
  orderRows,
  consoleErrors: errors,
  screenshot: shot,
}
console.log(JSON.stringify(result, null, 2))
if (errors.length || canvasCount < 1) {
  console.error('REAL E2E SHOT FAILED')
  process.exit(1)
}
console.log('REAL E2E SHOT OK')
