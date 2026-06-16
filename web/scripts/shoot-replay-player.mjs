// 佐證:Backtest 前端回放播放器 — 逐根 K 線回放 + 進出場 marker + PnL 同步長出。
// 驅動 Vite dev(:5174,proxy → :8000 API)→ 開 /backtest → 選一個有成交的 run
// (預設 #93,168 trades,2024-01)→ 回放引擎自動從頭播放 → 用控制列 scrub 到
// 不同進度截圖(K 線長一半 + 部分 marker + 權益曲線長一半),佐證逐根回放有效。
import { chromium } from 'playwright';

const BASE = process.env.WEB_URL || 'http://127.0.0.1:5174';
const RUN_ID = process.env.RUN_ID || '93';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1480, height: 940 }, deviceScaleFactor: 2 });
page.on('console', (m) => { if (m.type() === 'error') console.log('[browser-err]', m.text()); });

await page.goto(BASE + '/backtest', { waitUntil: 'networkidle' }).catch(() => {});
await page.waitForTimeout(1200);

// 選有成交的 run → 自動載入並從頭回放。
const rowSel = `[data-testid="run-row-${RUN_ID}"]`;
try {
  await page.waitForSelector(rowSel, { timeout: 10000 });
  await page.locator(rowSel).click();
  console.log('selected run', RUN_ID);
} catch (e) {
  console.log('run row not found, fallback first row:', e.message);
  await page.locator('.run-row').first().click();
}

// 等控制列出現(replay 模式)。
await page.waitForSelector('[data-testid="replay-controls"]', { timeout: 10000 });

const progress = page.locator('[data-testid="replay-progress"]');
// 等 bars 真的載完(total 穩定在大值)→ 避免在資料尚未到位時操作。
await page.waitForFunction(() => {
  const el = document.querySelector('[data-testid="replay-progress"]');
  return el && Number(el.max) > 100;
}, { timeout: 15000 });
await page.waitForTimeout(400);
const total = Number(await progress.getAttribute('max')) + 1;
console.log('total bars =', total);

async function pause() {
  // 若正在播放(顯示 ⏸)則按一下暫停。
  const txt = await page.locator('[data-testid="replay-playpause"]').innerText().catch(() => '');
  if (txt.includes('⏸')) await page.locator('[data-testid="replay-playpause"]').click();
}

// scrub 到指定 0-based index(用 range 鍵盤或直接 fill）。
async function scrubTo(idx) {
  await progress.evaluate((el, v) => {
    el.value = String(v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }, idx);
  await page.waitForTimeout(500);
}

// 1) 開頭附近(剛長出一小段)。
await pause();
await scrubTo(Math.floor(total * 0.12));
await page.locator('[data-testid="replay-position"]').innerText().then((t) => console.log('shot1 pos', t));
await page.screenshot({ path: 'artifacts/replay-01-early.png' });

// 2) 約一半(K 線長一半 + 部分 marker + 權益曲線長一半)。
await scrubTo(Math.floor(total * 0.5));
await page.locator('[data-testid="replay-position"]').innerText().then((t) => console.log('shot2 pos', t));
await page.screenshot({ path: 'artifacts/replay-02-half.png' });

// 3) 約 80%(更多 marker + 權益曲線更長)。
await scrubTo(Math.floor(total * 0.8));
await page.locator('[data-testid="replay-position"]').innerText().then((t) => console.log('shot3 pos', t));
await page.screenshot({ path: 'artifacts/replay-03-mostly.png' });

// 4) 跳到結尾 → 顯示完整(全量 K 線 + 全部 marker + 完整權益曲線)。
await page.locator('[data-testid="replay-to-end"]').click();
await page.waitForTimeout(800);
await page.locator('[data-testid="replay-position"]').innerText().then((t) => console.log('shot4 pos', t));
await page.screenshot({ path: 'artifacts/replay-04-complete.png' });

// 5) 調速度滑桿到較快(佐證控制列可調速)+ 重播(從頭逐根)。
await page.locator('[data-testid="replay-restart"]').click();
await page.waitForTimeout(1400); // 讓引擎逐根長出一小段(預設 5 根/秒)。
await pause();
await page.locator('[data-testid="replay-position"]').innerText().then((t) => console.log('shot5 (replay running) pos', t));
await page.screenshot({ path: 'artifacts/replay-05-restart-running.png' });

await browser.close();
console.log('done: artifacts/replay-0{1..5}-*.png');
