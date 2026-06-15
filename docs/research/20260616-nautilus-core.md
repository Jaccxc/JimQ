# 研究:NautilusTrader 核心架構

> 來源:官方文件 `nautilustrader.io/docs` + GitHub `develop` 原始碼。整理於 2026-06-16。
> 用途:JimQ 以 NautilusTrader 為交易引擎基底,本文記錄其核心能力與設計,供架構決策參考。

## 1. 整體架構:Rust 核心 + Python/Cython 控制層

- 混合系統:**Rust-native 核心**提供確定性、事件驅動的 runtime;**Python 作為控制層**負責策略邏輯、設定與編排。
- 程式碼分層:`crates/`(Rust)、`nautilus_trader/`(Python + Cython `.pyx`)。
- 綁定機制有兩條路徑並存,正在從 **Cython → PyO3** 遷移(目標:安裝時不需 Rust toolchain)。任一元件「是 Rust 還是 Cython」要看版本。
- 設計原則:DDD、事件驅動、**Ports and Adapters(六邊形架構)**、crash-only 設計。品質屬性優先序:**可靠性 > 效能 > 模組化 > 可測試性 > 可維護性 > 可部署性**。
- 效能模型仿 **LMAX 架構**:
  - **單執行緒 kernel**:策略邏輯、訂單管理、風控、cache 都在同一執行緒處理 → **確定性事件排序**(backtest/live 一致性的根基)。
  - **背景服務**(網路 I/O、持久化、venue adapters)在獨立執行緒 / tokio runtime,透過 MPSC channel + MessageBus 回到 kernel。
  - 價格/數量用定點數運算;Parquet/Arrow 欄式持久化。

## 2. 核心元件

| 元件 | 職責 |
|---|---|
| **NautilusKernel** | 中央編排器,初始化並管理所有元件,設定 messaging,維護環境別行為(backtest/sandbox/live)。三種環境共用同一核心。 |
| **MessageBus** | 元件間通訊骨幹:Pub/Sub、Request/Response、Point-to-Point。承載 Data / Events / Commands。可選 Redis 持久化/串流。 |
| **Cache** | 高效記憶體儲存:instruments、currencies、accounts、orders、positions、市場資料 + 任意自訂物件。可選 Redis backing。 |
| **Clock** | 奈秒級時間抽象,含 timer/alert。backtest 用 `TestClock`(手動推進),live 用 `LiveClock`。timer API 兩者相同。 |
| **DataEngine** | 處理並路由市場資料給訂閱者;聚合(如建 bar)後再發佈。接 venue `DataClient` adapter。 |
| **ExecutionEngine** | 管理訂單生命週期:路由交易指令到 `ExecutionClient`,追蹤訂單/部位狀態,處理成交與對帳(reconciliation)。 |
| **RiskEngine** | 策略與 ExecutionEngine 之間的事前風控閘:事前驗證、rate-limiting、名目上限、曝險監控。 |

指令/事件流:策略發指令 → MessageBus → **RiskEngine**(驗證+限速)→ **ExecutionEngine**(路由到 client)→ venue。成交回流:ExecutionClient → ExecutionEngine → MessageBus 事件 + Cache 更新 → 策略 `on_event`。

風控預設:`max_order_submit_rate="100/00:00:01"`、`max_notional_per_order`(dict)。即使 `bypass=True` 仍會檢查重複 ID。
Live 執行引擎含完整對帳機制:`reconciliation=True`、`inflight_check_interval_ms=2000`、`reconciliation_startup_delay_secs=10.0` 等。

## 3. MessageBus

- 三種模式(P2P / Pub-Sub / Req-Resp)× 三種訊息類別(Data / Events / Commands)。
- 階層式字串 topic,例:`data.book.deltas.XCME.ESZ24`。訊息**不可變**。
- **外部 backing = Redis**(需 6.2+ 支援 Streams)。訊息序列化後丟到 MPSC channel,由獨立 Rust 執行緒寫入,不阻塞主執行緒。
- 序列化:`encoding="msgpack"`(預設,最佳)或 `"json"`(可讀)。自訂型別用 `register_serializable_type`。
- `MessageBusConfig` 關鍵欄位:`database`、`encoding`、`streams_prefix="stream"`、`stream_per_topic=True`(Redis 相容請設 **False**)、`external_streams`、**`types_filter`**(排除 QuoteTick/TradeTick 等高頻型別避免淹沒)、`autotrim_mins`。

## 4. 交易領域模型與資料型別

- **Instruments**:約 20 種具體型別(現貨、期貨、永續、選擇權、betting、synthetic 等)。`InstrumentId = {Symbol}.{Venue}`,例 `ETHUSDT-PERP.BINANCE`。精度嚴格強制。
- **Orders**:9 種型別(Market/Limit/StopMarket/StopLimit/MarketToLimit/MarketIfTouched/LimitIfTouched/TrailingStopMarket/TrailingStopLimit)。TIF:GTC/IOC/FOK/GTD/DAY/AT_THE_OPEN/AT_THE_CLOSE。
  - 執行指示:`post_only`、`reduce_only`、`display_qty`(iceberg)、`expire_time`。
  - **Contingent orders**:**OTO**(one-triggers-other,bracket 進場→TP/SL 的基礎)、**OCO**、**OUO**。用 `OrderFactory` 建構。
  - **Order emulation**:可用原生 MARKET/LIMIT 在本地模擬 venue 不支援的單型。
- **Positions**:side/quantity/avg_px_open/realized_pnl/unrealized_pnl 等。**OMS 型別**:`NETTING`(每 instrument 一個部位)vs `HEDGING`(可同時多空)。
- **Accounts**:`CASH` / `MARGIN`(可設 leverage)/ `BETTING`。`total == locked + free`。
- **市場資料型別**:
  - **Bar** = OHLCV;`BarType = InstrumentId + BarSpecification + AggregationSource`;15 種 `BarAggregation`(Tick/Volume/Value/Renko/時間)。`AggregationSource`:External(venue)/Internal(Nautilus 自建)。
  - **QuoteTick**、**TradeTick**、**OrderBook**(L1/L2/L3,delta 串流)、MarkPrice/IndexPrice/FundingRate 等。
  - **自訂資料**:繼承 `Data`,或用 `@customdataclass` 自動生成序列化。
  - **時間戳**:`ts_event`(事件發生)vs `ts_init`(物件建立);backtest 依 `ts_init` 穩定排序。

## 5. Actor 與 Strategy 模型

- `Strategy` **繼承 `Actor`**。
  - **Actor**:資料訂閱/請求、事件處理/發佈、timer、**唯讀** cache/portfolio、logging。**不能下單**。適合自訂資料源、訊號發佈、指標聚合、風控監控。
  - **Strategy**:加上下單能力(`submit_order`/`cancel_order`/`modify_order`/`market_exit` 等)+ `OrderFactory`。
- 生命週期 handler:`on_start`/`on_stop`/`on_resume`/`on_reset`/`on_degrade`/`on_fault`/`on_dispose`。
- 事件/資料 handler:`on_bar`/`on_quote_tick`/`on_trade_tick`/`on_order_book`/`on_data`(自訂)/`on_historical_data`/`on_order_filled`/`on_event`(catch-all)。
- 訂閱:`subscribe_bars`/`subscribe_quote_ticks`/...;歷史拉取用 `request_*` → `on_historical_data`。
- 指標在 `on_start` 註冊(`register_indicator_for_bars` 等),資料到達自動更新。

## 6. Backtest vs Live —「同一份碼」保證

- 三種環境:**Backtest**(歷史+模擬 venue)、**Sandbox**(即時資料+模擬 venue)、**Live**(即時資料+真實 venue,可紙上或真錢)。
- Backtest 兩種 API:
  - 低階 **`BacktestEngine`**:`add_venue`(oms_type/account_type/starting_balances/fill_model/latency_model)→ `add_instrument`/`add_data` → `add_strategy` → `run()` → reports → `reset()`/`dispose()`。
  - 高階 **`BacktestNode`**:設定驅動,可串流大資料集(`chunk_size`)。`BacktestRunConfig`(venues/data/engine)、`BacktestVenueConfig`、`BacktestDataConfig`(從 catalog 讀)。
  - venue 模擬:`FillModel`(成交機率/滑點)、latency model、margin model。
- Live **`TradingNode`**:`TradingNodeConfig` 帶 `data_clients`/`exec_clients`(venue→adapter 設定)。用 factory 註冊 adapter,`node.build(); node.run()`。啟動時對帳。
- **同一份碼保證**:三環境共用 `NautilusKernel`/MessageBus/Cache/引擎。**變的只是設定與 adapter,策略邏輯不變**。
- ⚠️ **但 parity 是架構性的、非絕對**:受限於模擬擬真度(fill/latency model)與 live 非確定性(網路抖動、部分成交、拒單)。建議流程:backtest 建模 latency/fill → sandbox 驗證 → 原封不動上 live。

## 7. 資料 Catalog 與持久化

- **`ParquetDataCatalog`**:Parquet(欄式)+ Arrow schema。核心型別走 Rust backend,自訂型別走 PyArrow fallback。透過 fsspec 支援 local/S3/GCS/Azure。
- 階層式分區:`<catalog>/data/<type>/<identifier>/<start>-<end>.parquet`;檔名編碼時間區間 → 時間切片查詢可剪枝檔案。
- 寫入 `write_data`(需依 `ts_init` 單調遞增);查詢 `query(data_cls, identifiers, start, end, where=...)` 支援 predicate pushdown。
- **Wranglers**:把 pandas DataFrame 轉成 Nautilus 物件(QuoteTick/TradeTick/Bar/OrderBookDelta)。
- ⚠️ **重要**:catalog 已**移除 DataFrame helper**(回傳 Nautilus 物件,非 DataFrame)。要做訓練資料,需直接讀底層 Parquet 進 pandas/Polars,或查 Nautilus 物件後 `to_dict()` 轉 DataFrame。
- Backtest 結果可用 `StreamingConfig` 串流到 feather → 轉 Parquet 查詢。

## 給工程師的跨切面重點

1. **確定性就是產品**。單執行緒 LMAX kernel + 奈秒 Clock + 穩定 `ts_init` 排序 = backtest 與 live 同一條路徑。策略寫成純事件 handler,所有 I/O 推到 adapter。
2. **Ports-and-adapters 是整合契約**。新 venue = 實作 `DataClient`/`ExecutionClient` + factory,其餘全部複用。
3. **Cython→Rust/PyO3 遷移進行中**。pin 一個 release,依賴前用原始碼確認簽章。
4. **Redis 是可選基礎設施**(backing MessageBus streams 與 Cache 狀態),非必要。高頻資料用 `types_filter` + `stream_per_topic=False` 控管。
5. **Parity 有極限**。投資在擬真 `FillModel`/`LatencyModel`,用 sandbox 當上線前的關卡。
