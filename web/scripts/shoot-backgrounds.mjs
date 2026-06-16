// 截圖 5 種可切換背景(改版:讓 glassmorphism 顯現)在 /ui-preview 上的效果。
// 切換方式:eval 設 document.documentElement data-bg(等同 BackgroundPicker 套用機制)。
import { chromium } from 'playwright';

const BASE = process.env.WEB_URL || 'http://127.0.0.1:5173';
const bgs = ['aurora', 'orbs', 'grain', 'grid', 'minimal'];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await page.goto(BASE + '/ui-preview', { waitUntil: 'networkidle' }).catch(() => {});
for (const bg of bgs) {
  await page.evaluate((id) => document.documentElement.setAttribute('data-bg', id), bg);
  await page.waitForTimeout(700);
  const out = `artifacts/bg-${bg}.png`;
  await page.screenshot({ path: out, fullPage: false });
  console.log('shot', out);
}
// header BackgroundPicker 開啟態(在 /live)。
await page.goto(BASE + '/live', { waitUntil: 'networkidle' }).catch(() => {});
await page.evaluate(() => document.documentElement.setAttribute('data-bg', 'aurora'));
await page.waitForTimeout(400);
const trigger = await page.$('[data-testid="bg-picker-trigger"]');
if (trigger) {
  await trigger.click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: 'artifacts/bg-picker-open.png', fullPage: false });
  console.log('shot artifacts/bg-picker-open.png');
}
await browser.close();
