## Problem Statement

JimQ 的目標是用量化交易賺錢,基底已選定 NautilusTrader,並在 `docs/` 完成研究與架構定案。但目前 repo 只有文件、沒有任何可運行的程式。在投入 DL/RL 與複雜策略之前,我們需要先證明「一條交易訊號能從歷史資料,一路流經引擎、串流匯流排、後端、前端,最終在 K 線圖上看到進場/停損/停利」這條**端到端垂直切片**是通的、可信任的、可重複的。

沒有這條 tracer bullet,後續所有複雜度(多模型、RL、另類資料)都建在未驗證的地基上,失敗時無法分辨是策略問題還是管線問題。

## Solution

建立 JimQ 的 Phase 0 地基與 Phase 1 tracer bullet:一個 monorepo(uv workspace)+ docker-compose(Redis、PostgreSQL),把 NautilusTrader 引擎裝起來,從 Binance 抓 BTCUSDT 永續的歷史 K 線與資金費率灌進 ParquetDataCatalog,跑一條最簡單的雙 EMA 交叉策略(含 bracket OTO 設停損/停利)的 backtest。backtest 的事件(bar、order、fill、position、PnL)經 Nautilus MessageBus → Redis Streams,由 FastAPI 後端(fork 自 benavlabs/FastAPI-boilerplate v0.15.0、剝除 user/tier/auth)的 consumer 讀取、正規化後經 WebSocket 推到 Vue 3 + Lightweight Charts 前端,即時 replay 顯示 K 線、進場箭頭、停損/停利水平線與 PnL。

範圍**僅 backtest 端到端**;sandbox/testnet 與 live 真錢推遲到 Phase 2。即便是 backtest,也走**真正的串流路徑**(Redis Streams replay),以在第一期就驗證整套串流架構,而非只做靜態批次顯示。

## User Stories

1. As a 開發者, I want 一個 monorepo + uv workspace 骨架(libs/jimq_core、engine、api 為 workspace members;research 獨立 venv), so that 各套件能共用型別與特徵碼且依賴清楚。
2. As a 開發者, I want docker-compose 一鍵起 Redis 與 PostgreSQL, so that 我不必手動安裝服務即可在本機跑通整套。
3. As a 開發者, I want pin 版的 NautilusTrader 在 Python 3.12 環境裝起來並通過匯入/版本驗證, so that 引擎基底穩定可重現。
4. As a 量化研究者, I want 一支腳本從 Binance 抓 BTCUSDT-PERP 的歷史 K 線(1m/5m)與資金費率, so that 我有資料可做 backtest。
5. As a 量化研究者, I want ingest 把交易所原始資料轉成 Nautilus 物件並寫入 ParquetDataCatalog, so that 引擎能以原生格式讀取且資料可重複載入。
6. As a 量化研究者, I want 從 catalog 依時間區間與 instrument 查詢資料, so that backtest 與未來訓練都能取到正確切片。
7. As a 量化研究者, I want 一條雙 EMA 交叉策略,交叉進場、用 bracket(OTO)同時掛停損與停利, so that 我能驗證下單、成交、部位、出場的完整生命週期。
8. As a 量化研究者, I want EMA 等特徵計算放在共用特徵庫(libs/jimq_core/features), so that engine 推論與 research 訓練用同一份特徵碼,消除 train/serve skew。
9. As a 量化研究者, I want 跑 backtest 並產出帳戶/訂單/部位報表, so that 我能確認策略行為與損益。
10. As a 開發者, I want backtest 的 bar/order/fill/position/PnL 事件經 MessageBus 發佈到 Redis Streams(types_filter 排除高頻 tick), so that 外部服務能消費引擎狀態而不需侵入引擎。
11. As a 後端開發者, I want fork benavlabs/FastAPI-boilerplate v0.15.0 並剝除 user/tier/auth/ARQ/admin, so that 我有乾淨的 async FastAPI 地基而無多餘的身份與計費機制。
12. As a 後端開發者, I want 保留 boilerplate 的 async SQLAlchemy、設定管理、cache、例外處理、Alembic、FastCRUD 模式, so that 基礎設施經過驗證可直接複用。
13. As a 後端開發者, I want 一個 consumer task 以 XREADGROUP 讀 Nautilus Redis Streams、反序列化並正規化為 DTO, so that 引擎事件能進入後端的 in-process hub。
14. As a 後端開發者, I want 一個 in-process pub/sub hub 把正規化事件分派給訂閱者, so that WebSocket 連線能取得對應 channel 的更新。
15. As a 後端開發者, I want 一個 WebSocket gateway 提供多工 channel、連線即推快照後送 delta、有界佇列與 last_seq 補洞、心跳, so that 前端能可靠地接收即時串流。
16. As a 後端開發者, I want REST 端點查詢歷史 bars(從 catalog), so that 前端載入圖表時能先取得歷史 K 線。
17. As a 後端開發者, I want Postgres 只存應用資料(此期至少 backtest_run 摘要), so that 我能保存與查詢 backtest 結果。
18. As a 交易者, I want Vue 3 + Vite + TS + Pinia 前端用 Lightweight Charts v5 顯示 K 線, so that 我能視覺化行情。
19. As a 交易者, I want 圖上以箭頭標記進場、以水平線標記停損與停利, so that 我能一眼看出每筆交易的進出場位置。
20. As a 交易者, I want 即時看到 backtest replay 的部位與 PnL, so that 我能觀察策略運行過程。
21. As a 交易者, I want 前端透過 WebSocket 訂閱並在斷線時自動重連(指數退避 + last_seq), so that 串流中斷不會遺漏事件。
22. As a 開發者, I want 整套能用 docker-compose 啟動並從文件化的步驟跑通一次完整 demo, so that 任何人都能重現端到端結果。
23. As a 開發者, I want ingest→catalog 模組有測試(資料轉換正確、寫入後查得回、時間排序), so that 資料層可信。
24. As a 開發者, I want 共用特徵庫 features 有測試(EMA 等計算正確、增量與整批一致), so that 特徵不會在 engine 與 research 間漂移。
25. As a 開發者, I want Redis consumer→hub 轉換有測試(序列化訊息正確反序列化並正規化為 DTO), so that 串流邊界可信。
26. As a 開發者, I want WS gateway 套件邊界有測試(多工分派、快照+delta、有界佇列丟棄/合併、last_seq 補洞), so that 即時層在壓力與重連下行為正確。

## Implementation Decisions

**整體架構與決策依據**:`docs/design/20260616-1830-decisions-confirmed.md`、`docs/design/20260616-1845-repo-structure-final.md`。

- **Monorepo + uv workspace**:members 為 `libs/jimq_core`、`engine`、`api`;`research` 因 CUDA 重依賴使用獨立 venv(本 PRD 不含 research 實作)。
- **服務**:docker-compose 起 `redis`(≥6.2,供 Nautilus Cache + MessageBus Streams)與 `postgres`(應用資料)。boilerplate 的 Redis cache 使用**不同 DB index**,與 Nautilus message bus 隔離。
- **引擎**:pin 版 NautilusTrader(stable PyPI wheel),Python 3.12。第一期用低階或高階 BacktestEngine/BacktestNode 跑 backtest;venue 設 NETTING/MARGIN、設 FillModel 與 latency model(可用預設)。
- **資料**:`jimq_core` 提供共用 DTO 與特徵庫。ingest 模組將 Binance BTCUSDT-PERP klines + funding rate 轉成 Nautilus 物件,經 wrangler 寫入 ParquetDataCatalog;依 ts_init 單調遞增。查詢以 instrument + 時間區間。
- **策略**:雙 EMA 交叉(fast/slow),於 `on_bar` 偵測交叉;進場用 OrderFactory 建 bracket(OTO)同時掛 SL/TP。EMA 計算呼叫 `jimq_core.features`(engine 與 research 共用)。
- **串流出**:`MessageBusConfig(database=Redis, stream_per_topic=False, types_filter=[QuoteTick, TradeTick])` 將 bar/order/fill/position/account 事件寫入 Redis Streams。stream key 採預設 `trader:{trader_id}:{instance_id}:{prefix}`。
- **命令路徑**:本期 backtest 不需即時控制;control command stream 的完整實作推遲到 Phase 2(可預留介面)。
- **後端**:fork benavlabs/FastAPI-boilerplate **v0.15.0 classic**(MIT)。KEEP:async SQLAlchemy 2.0、`core/config`(精簡掉 Crypt/FirstUser/CRUDAdmin/Tier mixin)、`core/setup`(移除 superuser docs gate)、`core/utils/cache`、exceptions、middleware、FastCRUD、Alembic。STRIP:users/posts/tiers/rate_limit/login/logout/security/token_blacklist/admin/`create_first_*`/ARQ worker。rate-limiter 因依賴 user/tier 改為 flat IP 級或移除。
- **後端模組**:
  - `services/nautilus_consumer`:XREADGROUP 讀 Redis Streams、反序列化 Nautilus 型別、正規化為 `jimq_core` DTO、發佈到 hub。
  - `services/hub`:in-process topic→queue 的 pub/sub。
  - `services/store`:從 catalog 查歷史 bars(非阻塞,必要時 threadpool)。
  - `ws/stream`:WebSocket gateway,多工 channel、連線快照+delta、有界佇列(溢出丟舊/合併)、last_seq 補洞、心跳。
  - REST:歷史 bars 查詢;backtest_run 摘要 CRUD(FastCRUD)。
- **資料模型(Postgres,本期最小)**:`backtest_run`(執行 metadata 與結果摘要)。`strategy`/`trade_journal`/`model_registry` 結構可預留但非本期必要。
- **DTO 信封**:WebSocket 訊息採 `{channel, seq, data}`;channel 至少含 `bars`、`orders`、`fills`、`positions`、`pnl`。
- **前端**:Vue 3 + Vite + TS + Pinia + Vue Router。Lightweight Charts v5;chart/series 實例置於 Vue 響應式之外。`useTradeSocket` composable 管理連線/重連/分派到 Pinia stores。進場以 `createSeriesMarkers` 箭頭、SL/TP 以 `createPriceLine` 水平線、歷史 bars 以 REST 載入後 `series.update` 串流。前端顯示 TradingView 標註。型別由 FastAPI OpenAPI 生成對齊。

## Testing Decisions

**好測試的定義**:只測外部可觀察行為(輸入→輸出、邊界契約),不測實作細節;測試應在重構內部時仍然成立。優先測「深模組」——封裝複雜度、介面簡單穩定者。

**要測的模組(經使用者確認)**:
1. **ingest → catalog**:給定交易所原始 klines/funding,轉換後的 Nautilus 物件欄位正確、寫入 catalog 後可依時間區間查回、且時間單調排序。prior art:Nautilus wrangler 的 DataFrame→物件轉換模式。
2. **共用特徵庫 `features`**:EMA 等計算數值正確;增量更新與整批計算結果一致(反 skew 的關鍵保證)。
3. **Redis consumer → hub 轉換**:給定序列化的 Nautilus 串流訊息(msgpack),正確反序列化並正規化為 DTO 信封;未知/被 filter 的型別處理得當。
4. **WS gateway 套件邊界**:多工 channel 正確分派;連線先收快照再收 delta;有界佇列在溢出時丟舊或合併(last-value-wins for PnL/positions);斷線重連帶 last_seq 能補洞不重複不遺漏。

測試以行為層級為主(餵資料、斷言輸出/序列),避免綁定內部函式簽章。整合測試可用 docker-compose 起的 Redis 驗證 consumer↔stream 真實往返(prior art:boilerplate 既有 pytest 設定)。

## Out of Scope

- Sandbox/testnet 即時資料與 live 真錢交易(Phase 2)。
- 從 dashboard 下達控制命令(start/stop/調參/kill switch)的完整實作(Phase 2;本期可預留介面)。
- 任何 DL/RL 訓練、research 套件實作、自訂 perp Gym 環境、TorchTrade 探勘(Phase 4/5)。
- 另類資料(衛星等)Actor(Phase 6)。
- 多策略/多 instrument、策略參數版本化 UI、模型登記。
- 認證/多使用者/權限(已從 boilerplate 剝除,且本期單機單人)。
- 進階風控(名目上限/rate limit 細則)、對帳機制(屬 live)。
- 生產級部署、CI/CD、k8s、物件儲存(MinIO/S3)。
- FX 市場(加密永續之後才接)。

## Further Notes

- 依 A3,本切片的價值在於**證明管線可信**,而非策略獲利;EMA cross 只是載具。
- 即使 backtest 也走 Redis Streams replay,是刻意要在第一期就驗證真正的串流架構,避免日後 live 才發現串流層問題。
- `jimq_core.features` 是反 train/serve skew 的基石,務必由 engine 與未來 research 共用。
- Nautilus 的 catalog 已移除 DataFrame helper;ingest 需直接處理 Parquet 或 Nautilus 物件。
- boilerplate 有兩個版本,務必鎖定 **v0.15.0 classic**(非 main/v0.18.0 的重寫版)。
- 後續流程:此 PRD → `/prd-to-issues` 切成可獨立抓取的垂直切片 issues → `ultra-tdd` 依鐵律契約 TDD 開發。
