/**
 * 卡 #23 (W4) — Research 頁 headless 視覺佐證(best-effort)。
 *
 * 不需真後端:本腳本自帶
 *  1) 靜態伺服 dist/(vite build 產物)。
 *  2) mock REST:
 *     - GET /api/v1/models            → FastCRUD 分頁 {data:[ModelRecord]}。
 *     - GET /api/v1/mlflow/experiments → [ExperimentRecord]。
 *     - GET /api/v1/mlflow/runs        → 攤平 [MlflowRun]。
 *     - POST /api/v1/research/jobs     → {job_id, correlation_id, status}。
 *  3) Playwright(home cache chromium)headless 載入 /research → 等三塊渲染 →
 *     點「Build dataset」觸發 job → 截圖到 web/artifacts/ → console error 即失敗。
 *
 * 形狀對齊 api ModelRegistryRead / mlflow proxy / ResearchJobAccepted。
 */
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const DIST = path.join(ROOT, 'dist')
const ARTIFACTS = path.join(ROOT, 'artifacts')
fs.mkdirSync(ARTIFACTS, { recursive: true })

const PORT = 4322
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' }

const MODELS = {
  data: [
    { id: 1, name: 'ppo_btc_perp', version: 'v1', framework: 'STABLE_BASELINES3', metrics: { sharpe: 1.42 }, sharpe: '1.42', created_at: '2026-06-16T00:00:00Z' },
    { id: 2, name: 'ema_baseline', version: 'v2', framework: 'SKLEARN', metrics: { sharpe: 0.83 }, sharpe: '0.83', created_at: '2026-06-15T12:30:00Z' },
  ],
  total_count: 2,
}
const EXPERIMENTS = [
  { experiment_id: '1', name: 'backtest', lifecycle_stage: 'active' },
  { experiment_id: '2', name: 'train', lifecycle_stage: 'active' },
]
const RUNS = [
  { run_id: 'abc123', run_name: 'ema-3-8', experiment_id: '1', status: 'FINISHED', start_time: 1700000000000, params: { fast_period: '3', slow_period: '8' }, metrics: { sharpe: 1.5, total_return: 0.1 } },
  { run_id: 'def456', run_name: 'ema-5-13', experiment_id: '1', status: 'FINISHED', start_time: 1700001000000, params: { fast_period: '5', slow_period: '13' }, metrics: { sharpe: 2.1, total_return: 0.32 } },
]

function json(res, payload) {
  res.writeHead(200, { 'content-type': 'application/json' })
  res.end(JSON.stringify(payload))
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)
  const p = url.pathname
  if (p === '/api/v1/models') return json(res, MODELS)
  if (p === '/api/v1/mlflow/experiments') return json(res, EXPERIMENTS)
  if (p === '/api/v1/mlflow/runs') {
    const eid = url.searchParams.get('experiment_id')
    return json(res, RUNS.filter((r) => r.experiment_id === eid))
  }
  if (p === '/api/v1/research/jobs' && req.method === 'POST') {
    return json(res, { job_id: 101, correlation_id: 'corr-headless', status: 'PENDING' })
  }
  // static dist
  let fp = path.join(DIST, p === '/' ? '/index.html' : p)
  if (!fs.existsSync(fp)) fp = path.join(DIST, 'index.html') // SPA fallback
  const ext = path.extname(fp)
  fs.readFile(fp, (err, buf) => {
    if (err) { res.writeHead(404); res.end('not found'); return }
    res.writeHead(200, { 'content-type': MIME[ext] ?? 'application/octet-stream' })
    res.end(buf)
  })
})

const errors = []
await new Promise((r) => server.listen(PORT, r))
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))

await page.goto(`http://localhost:${PORT}/research`, { waitUntil: 'networkidle' })
await page.waitForSelector('[data-testid="research-dashboard"]', { timeout: 15000 })
// 等 Models 表與 MLflow runs 表有資料列(REST mock 生效佐證)。
await page.waitForFunction(() => {
  const m = document.querySelectorAll('[data-testid="models-table"] tbody tr').length
  const r = document.querySelectorAll('[data-testid="mlflow-runs-table"] tbody tr').length
  return m >= 1 && r >= 1
}, { timeout: 8000 })

// 觸發 job → 等狀態出現。
await page.click('[data-testid="trigger-build-dataset"]')
await page.waitForSelector('[data-testid="last-job-status"]', { timeout: 8000 })

const shot = path.join(ARTIFACTS, 'w4-research-dashboard.png')
await page.screenshot({ path: shot, fullPage: false })

const modelRows = await page.locator('[data-testid="models-table"] tbody tr').count()
const runRows = await page.locator('[data-testid="mlflow-runs-table"] tbody tr').count()
const jobStatus = (await page.locator('[data-testid="last-job-status"]').textContent())?.trim()

await browser.close()
server.close()

const result = { modelRows, runRows, jobStatus, consoleErrors: errors, screenshot: shot }
console.log(JSON.stringify(result, null, 2))
if (errors.length || modelRows < 1 || runRows < 1 || !jobStatus) {
  console.error('VERIFY FAILED')
  process.exit(1)
}
console.log('VERIFY OK')
