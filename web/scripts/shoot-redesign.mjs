// 截圖 glassmorphism 改版後各頁(/ui-preview 自足、其餘頁殼+玻璃面板,無 backend 也可看設計)。
import { chromium } from 'playwright';

const BASE = process.env.WEB_URL || 'http://127.0.0.1:5173';
const targets = [
  { path: '/ui-preview', name: 'ui-preview' },
  { path: '/live', name: 'live' },
  { path: '/backtest', name: 'backtest' },
  { path: '/research', name: 'research' },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
for (const t of targets) {
  await page.goto(BASE + t.path, { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(800);
  const out = `artifacts/redesign-${t.name}.png`;
  await page.screenshot({ path: out, fullPage: false });
  console.log('shot', out);
}
await browser.close();
