// 佐證:Backtest 開箱即用 — 動態預設日期 + catalog 同步 + 成交持久化 → 權益曲線。
// 驅動真 :8080 全棧 UI:開 /backtest(launcher 自動填有資料的日期)→ 選一個有成交
// 的 run → 截圖主圖 K 線 + 進出場 marker + 權益副圖。
import { chromium } from 'playwright';

const BASE = process.env.WEB_URL || 'http://127.0.0.1:8080';
const RUN_ID = process.env.RUN_ID; // 指定要選的有成交 run

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 980 }, deviceScaleFactor: 2 });
page.on('console', (m) => { if (m.type() === 'error') console.log('[browser-err]', m.text()); });

await page.goto(BASE + '/backtest', { waitUntil: 'networkidle' }).catch(() => {});
// 等 launcher 掛載 + fetch /bars/range 動態填日期。
await page.waitForTimeout(1500);

// 1) 佐證動態預設日期:讀 Start/End input 值(應為 2024-01,而非寫死 2023-11-14)。
const startVal = await page.locator('input[type="datetime-local"]').first().inputValue().catch(() => '');
const endVal = await page.locator('input[type="datetime-local"]').nth(1).inputValue().catch(() => '');
console.log('launcher default start =', startVal, 'end =', endVal);

// 2) 選一個有成交的 run(若給 RUN_ID 直接點該列;否則點第一列)。
const rowSel = RUN_ID ? `[data-testid="run-row-${RUN_ID}"]` : '.run-row';
try {
  await page.waitForSelector(rowSel, { timeout: 8000 });
  await page.locator(rowSel).first().click();
  console.log('selected run row', rowSel);
} catch (e) {
  console.log('run row not found:', e.message);
}
// 等 fetch trades + bars → 主圖重畫 + 權益副圖長出。
await page.waitForTimeout(2500);

const out = 'artifacts/backtest-data-ux.png';
await page.screenshot({ path: out, fullPage: false });
console.log('shot', out);

await browser.close();
