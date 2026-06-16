# Web 圖表:多標的 / 多週期 + EMA 疊圖(卡 #22 / W3)

本文件說明 web 儀表板的標的(symbol)/ 時間週期(timeframe)選擇器、EMA 指標疊圖,
以及如何用 `scripts/ingest_binance.py` 灌入更多標的資料。

## 功能總覽

- **標的選擇器**:`ChartControls.vue` 的下拉選單,清單來自 `chartSettings` store
  (`symbols`)。切換時觸發 `useChartData.switchTo` → 重載歷史 bars(`GET /api/v1/bars`)
  → 重訂串流(`useTradeSocket.disconnect → connect`)。
- **時間週期選擇器**:同上,目前提供 `1m` / `5m`。
- **EMA 疊圖**:fast / slow 兩條線可獨立開關並調整週期。前端用
  `web/src/lib/ema.ts` 的 `emaLineData`(與 `libs/jimq_core/jimq_core/features.py`
  的 `ema_batch` 同公式:`alpha = 2/(period+1)`、SMA 種子),消除 train/serve skew。

## 切換的圖表安全(無記憶體洩漏 / 重複 series)

- `ChartController`(`web/src/lib/chartController.ts`)的 chart / series 實例存於
  Vue 響應式之外。
- 切換 symbol / timeframe 時,`CandleChart.vue` 呼叫 `controller.reset()`:
  **重用同一個 chart 實例**,清空 candlestick 資料、移除所有 EMA line series、
  markers、priceLines,再由 bars watcher 以新歷史重畫。
- EMA line series 以 id(`fast` / `slow`)為鍵重用:同 id 重複 `setEmaLine` 只
  `setData` 同一個 series,不重複建立 → 不洩漏、不累積重複 series。
- headless 佐證(`web/scripts/verify-w3.mjs`)斷言切換前後 canvas 數量一致,
  確認無 series 累積。

## 可用標的(受限於 catalog 已灌資料)

`data/catalog` 目前主要為 **BTCUSDT-PERP.BINANCE**(1m / 5m)。

選擇器清單(`chartSettings` store)同時列出 `ETHUSDT-PERP.BINANCE` 作為多標的示範。
**選到尚未灌資料的標的時,`GET /api/v1/bars` 回空列表**,圖表會清空(reset)但
選擇器仍正常運作。要看到 ETH 的 K 線,需先灌資料(見下)。

## 灌入更多標的資料

`scripts/ingest_binance.py` 已支援 `--symbol`(預設 `BTCUSDT-PERP.BINANCE`)。
標的需先在 `engine/jimq_engine/catalog/instruments.py` 的 `_INSTRUMENT_FACTORIES`
註冊(目前已含 BTCUSDT-PERP / ETHUSDT-PERP)。

灌一小段 ETHUSDT-PERP 1m + 5m 示範:

```bash
uv run python scripts/ingest_binance.py \
    --symbol ETHUSDT-PERP.BINANCE \
    --start 2024-01-01 --end 2024-01-02 \
    --intervals 1m,5m
```

灌更多 BTCUSDT-PERP:

```bash
uv run python scripts/ingest_binance.py \
    --start 2024-01-01 --end 2024-01-07 --intervals 1m,5m --funding
```

說明:

- 公開資料免 API key,只連 Binance public REST,不碰本地 DB。
- idempotent:重複灌同一區間會先刪覆蓋區間再寫,不產生重複列。
- bar type 由 `--symbol` + interval 組出(如
  `ETHUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL`),與前端
  `GET /api/v1/bars?symbol=...&timeframe=...` 查詢對齊。

## 在選擇器加入新標的

1. 在 `instruments.py` 新增 instrument factory 並註冊到 `_INSTRUMENT_FACTORIES`。
2. 用上述 ingest 指令灌該標的資料。
3. 在 `web/src/stores/chartSettings.ts` 的 `DEFAULT_SYMBOLS` 加入 `{ value, label }`。
