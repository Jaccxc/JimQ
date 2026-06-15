# JimQ web — S7 前端(Vue 3 + Lightweight Charts v5)

BTCUSDT-PERP K 線儀表板:REST 載歷史、WS 串流即時 replay、進出場箭頭 + SL/TP 水平線、部位/PnL 面板。

獨立 npm 專案(不入 uv workspace)。Node 18 相容(Vite 5 / LWC v5.2)。

## 指令

```bash
npm install
npm run dev            # dev server(vite proxy /api→8000、/ws→8000)
npm run build          # vue-tsc 型別檢查 + vite build
npm run test           # Vitest 單元測試(36)
npm run verify:headless# Playwright headless 截圖(自帶 mock REST+WS,免後端)
```

## 後端接線(契約真相來源)

| 用途 | 端點 | 來源 |
|---|---|---|
| 歷史 bars | `GET /api/v1/bars?symbol=&timeframe=&start=&end=` → `BarDTO[]` | 卡 #8 `api/src/app/api/v1/bars.py` |
| 即時串流 | `WS /ws/stream?channels=&last_seq=&heartbeat_s=` 推 `{channel,seq,data}` | 卡 #7 `api/src/app/ws/stream.py` |

信封流(gateway):補洞 →(快照 `snapshot:true`)→ `{type:"live"}` → delta;閒置送 `{type:"heartbeat"}`。
channel ∈ `bars/orders/fills/positions/pnl`。事件 `data` 為 Nautilus 透傳純量 dict,帶 `type`
(payload 形狀對齊 `api/tests/test_nautilus_consumer.py`)。

`time` 欄位為 epoch 秒(LWC `UTCTimestamp`);`ts` 為 epoch 奈秒全精度。

## 架構

```
api/bars.ts ──(REST 歷史)──► stores/market ──┐
                                              ├─► CandleChart.vue ─(命令式)─► ChartController(LWC v5,響應式外)
useTradeSocket ─(WS)─► composables/dispatch ──┤
   │ 指數退避+jitter 重連                       ├─► stores/positions|orders|fills|pnl ─► panels/*
   │ last_seq 補洞(connection.lastSeq)        └─► stores/connection ─► ConnectionStatus
```

- **chart/series 實例置於 Vue 響應式之外**(`ChartController` 普通 class 存非響應式 `let`),元件 watcher 命令式餵 `setHistory`/`updateBar`/`addMarker`/`addPriceLine`。
- **進場** → `createSeriesMarkers` 箭頭;**SL/TP** → `series.createPriceLine` 水平線(由 fill/order 事件驅動,映射純函式 `lib/tradeMapping.ts`)。
- **TradingView 標註**:`layout.attributionLogo: true`(LWC Apache-2.0 授權要求)。

## 可測邏輯(Vitest,純函式/store/composable)

- `lib/tradeMapping`:order/fill → marker/priceLine 映射。
- `lib/backoff`:指數退避 + jitter。
- `stores/*`:六個 Pinia store 行為。
- `composables/dispatch`:信封 channel 路由 + snapshot/live/heartbeat + last_seq。
- `composables/useTradeSocket`:連線/重連/last_seq 補洞/分派(注入 FakeWebSocket + 假計時器)。
