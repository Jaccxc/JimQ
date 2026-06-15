# 研究:即時交易視覺化 Dashboard(Vue 3 + FastAPI)

> 整理於 2026-06-16。目標:K 線圖 + 交易標記(進場/SL/TP)、部位、PnL;後端 = NautilusTrader(Python)。單使用者、local-first,未來可能擴展。

## 1. K 線圖表庫

**建議:TradingView Lightweight Charts(主),klinecharts(備)。**

| 庫 | 授權 | 體積 | K 線 | 進場/SL/TP + 箭頭 | 評語 |
|---|---|---|---|---|---|
| **TradingView Lightweight Charts** | Apache-2.0(免費,**需標註**) | ~45KB | 極佳,專為金融 | `createPriceLine`(SL/TP/進場水平線)、`createSeriesMarkers`(箭頭)、custom series primitives | **整體最佳** |
| **klinecharts** | Apache-2.0(免費,**免標註**) | ~40KB | 極佳,交易優先 | 內建 overlay 繪圖系統 + 自訂 overlay | 強備案 |
| Apache ECharts | Apache-2.0 | 大 | 尚可,通用 | markLine/markPoint/graphic,但冗長需調效能 | 純 K 線太繁瑣 |
| Highcharts Stock | **商業** | 重 | 極佳 | 最佳註解 | 授權否決 |

- **Lightweight Charts** 對應需求乾淨:進場/SL/TP → `series.createPriceLine(...)`;交易箭頭 → v5 `createSeriesMarkers(series, [...])`;自訂(區間/陰影)→ series primitives;即時 → `series.update({...})` 更新最後一根或新增。
- ⚠️ **授權注意**:Apache-2.0 可商用,但**須顯示 TradingView 標註**(on-chart `attributionLogo` 或可見連結)。容易滿足,別偷拔。
- **版本**:目前 v5.x。v5 把 marker API 從 `series.setMarkers()` 改成獨立 `createSeriesMarkers`,用 v5 範例。
- **klinecharts** 備案:想要內建繪圖工具 UX(可拖曳趨勢線)且**免標註**時用,文件稍薄。
- **ECharts** 僅在同 app 還要許多非金融圖表(PnL 曲線、heatmap)時混用。

### Vue 3 整合
- Lightweight Charts 框架無關(操作 `<div>` ref)。包成薄元件:`onMounted` 建圖,**chart/series 實例存在非響應式變數**(別放 `reactive()`/`ref()`,否則 canvas 圖被 Vue 響應式包住會嚴重掉效能),命令式餵更新。官方有 Vue.js wrapper 教學。

## 2. 即時串流到前端

**建議:raw WebSocket(單一多工連線),不用 SSE,不用 socket.io。**

- 需多訊息型別(bars/ticks/order/position/PnL)**且**要送控制指令(start/stop、調參)回去 → 雙向多流是 WebSocket 經典場景;SSE 只能 server→client。
- **跳過 socket.io** — 較重、為舊瀏覽器 fallback;FastAPI 原生支援 WebSocket。(可保留小 SSE endpoint 做 log tailing。)
- 要實作的模式:
  1. **Topic 多工**:單 socket,每則訊息包封 `{channel, data}`,client 依 channel 路由,可 subscribe/unsubscribe。
  2. **連線即快照,再送 delta**:連上先推現有部位/開單/PnL + 近期 bars,再串增量。
  3. **每 client 有界佇列 + backpressure**:`asyncio.Queue(maxsize=N)`,溢出**丟舊或合併**(ticks/PnL last-value-wins),別阻塞 producer。
  4. **可續傳游標 `last_seq`**:事件帶單調序號,client 記最後序號,重連時打 HTTP 補洞 endpoint。
  5. **心跳 + 自動重連**:client 自寫指數退避+jitter 重連(瀏覽器 WebSocket API 不自動重連)。

## 3. FastAPI 後端結構

**建議:單一 async 服務,REST(查詢/控制)+ 一個 WebSocket gateway(串流),內部 pub/sub hub 由 Nautilus consumer task 餵。**

```
app/
  main.py                 # FastAPI app;lifespan 啟動 consumer + broadcaster task
  api/
    routes_bars.py        # GET /bars?symbol=&tf=&from=&to=(歷史)
    routes_positions.py   # GET /positions /orders /pnl
    routes_control.py     # POST /strategy/start|stop;PATCH 調參
    ws.py                 # WS /stream(多工 channel,快照+delta)
  services/
    hub.py                # in-process pub/sub:topic -> client queue set
    nautilus_consumer.py  # 讀 Nautilus Redis stream,正規化,publish 到 hub
    store.py              # 歷史 bar 查詢(Parquet/DuckDB/Timescale)
    control.py            # 送指令到引擎
  models/                 # Pydantic schema
```
- 用 **lifespan**(非 deprecated `@on_event`)啟動 consumer/broadcaster,關閉時清理。
- 歷史 bars:REST,read 路徑非阻塞(同步 store 用 `run_in_threadpool`/`asyncio.to_thread`)。
- 控制指令:REST `POST/PATCH`,回 202,結果狀態變化透過 WS 串回。
- 所有 payload(含 WS 信封)用 **Pydantic v2**。

## 4. FastAPI ↔ NautilusTrader 橋接

**建議:用 Nautilus 原生 Redis Streams message bus 當資料路徑(engine→FastAPI),控制路徑也用 Redis stream。** 因為 Nautilus 已原生說 Redis Streams,摩擦最小。

| 選項 | 持久化/重播 | 原生契合 Nautilus | 評語 |
|---|---|---|---|
| **Redis Streams** | 有(append-only log、consumer group、ack、at-least-once) | **有,內建** | **選用**。重啟存活,支援 `last_seq` 補洞,單一依賴 |
| Redis Pub/Sub | 無 | 部分 | 否決:斷線即丟失,無補洞 |
| ZeroMQ | 無內建持久化(吞吐 ~6×) | 非原生 | 否決:要自建橋且失去重播,速度非瓶頸 |
| 共用 Postgres/Timescale | 有,持久 | cache backend 但非低延遲串流 | 當**歷史 bar store**,不當 live bus |

- FastAPI `nautilus_consumer.py`:對 Nautilus stream key 做 `XREADGROUP` → 反序列化 → 正規化 → publish 到 hub → WebSocket。
- 命令路徑:FastAPI → 引擎,可用第二條 Redis stream 由 Nautilus 當 external command channel 消費,或節點內小型 command actor。
- **單使用者→未來擴展皆適用**:本地一個小依賴,日後多 worker 訂同一 Redis bus,免重架。歷史 bars 另存(本地 Parquet/DuckDB,日後 Timescale/Postgres)。

## 5. Vue 3 慣例(2026)

**工具:Vite + Vue 3(`<script setup>` Composition API)+ TypeScript + Pinia + Vue Router + Vitest。**
- `npm create vue@latest`,開 TS + Router + Pinia + Vitest。
- TS:把 WS 信封、bar/order/position DTO 型別化(理想從 FastAPI OpenAPI schema 生成,前後端同步)。
- **Pinia stores**:`useMarketStore`(bars,命令式餵圖)、`usePositionsStore`/`useOrdersStore`/`usePnlStore`、`useConnectionStore`(WS 狀態/`last_seq`)、`useStrategyStore`(參數/控制)。
- WebSocket client 當 composable/service(`useTradeSocket`),把進來的信封依 channel 派到對應 store;元件訂 store,不直接訂 socket。
- 元件結構:`chart/CandleChart.vue`(LWC wrapper)、`chart/PriceLines.vue`、`chart/TradeMarkers.vue`、`panels/PositionsTable.vue`/`OrdersTable.vue`/`PnlWidget.vue`、`controls/StrategyControls.vue`。
- ⚠️ **圖表 + 響應式規則**:chart/series 實例放在 Vue 響應式之外,更新用 chart 方法在 watcher/socket handler 內推。

### 開源參考
- SoybeanAdmin(Vue3+Vite+TS+Pinia admin 模板,MIT)、TradingView LWC Vue wrapper 教學、KLineChart-Pro。

## 底線架構

```
NautilusTrader node ──(MessageBusConfig → Redis Streams;types_filter 丟高頻 tick)──► Redis Streams
                                                                                          │ XREADGROUP
                                                                                          ▼
                                        FastAPI:nautilus_consumer task → in-process hub
                                              │                              │
                                  REST(bars/positions/orders/pnl/control)   WS /stream(多工:
                                              │                              快照+delta、last_seq、
                                              ▼                              有界佇列、心跳)
                                  歷史 store(DuckDB/Parquet 本地→Timescale)  │
                                                                              ▼
                                                            Vue 3(Vite+TS+Pinia):
                                                            useTradeSocket → stores →
                                                            Lightweight Charts(priceLines
                                                            + seriesMarkers + primitives)
```

**關鍵決策**:LWC v5(注意標註)做 K 線+標記;raw 多工 WebSocket 串流+控制;FastAPI async(REST + 一個 WS gateway,lifespan 管理 task);**Redis Streams 當 engine↔dashboard 橋(Nautilus 原生發佈、有持久化重播、從本地單人到多 worker 不變)**;Vue3+Vite+TS+Pinia,圖表實例置於響應式外。
