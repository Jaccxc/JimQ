# JimQ 系統架構總覽(草案 v0.1)

> 日期:2026-06-16 · 狀態:**草案,待 `/grill-me` 確認**
> 目標:用量化交易盡可能賺錢。平台需支援 live 交易、backtesting、策略開發,並能整合 DL/RL 與另類資料(衛星等)。基底 = NautilusTrader。

## 0. 設計原則

1. **Nautilus 做它最強的:確定性事件引擎 + research→live parity + 擬真執行。** 不硬塞它不擅長的(RL `step()` 訓練迴圈)。
2. **訓練與推論解耦。** GPU 上離線訓練(DL/RL),引擎內逐事件推論。權重是交付物。
3. **Redis Streams 是引擎與外圍世界的唯一接縫。** Dashboard、分析、命令都掛在這條。
4. **Local-first 單使用者,但別封死擴展路徑。** 用 docker-compose,選用日後能水平擴展的機制。
5. **先打通垂直切片(tracer bullet)再加複雜度。** 一條最簡策略要先跑通 backtest→sandbox→live + dashboard,才談 RL 與另類資料。

## 1. 高層元件圖

```
                        ┌─────────────────────────────────────────────┐
                        │                  研究 / 訓練層                 │
                        │  research/ (GPU)                              │
                        │  • 特徵工程 (從 Parquet catalog 讀)           │
                        │  • DL/RL 訓練 (Gym 環境, SB3/RLlib)           │
                        │  • 實驗追蹤 (MLflow?) + 模型登記              │
                        │  輸出: TorchScript/ONNX 權重 → model store    │
                        └───────────────┬─────────────────────────────┘
                                        │ 權重 artifact
                                        ▼
┌──────────────┐   歷史    ┌──────────────────────────┐   Redis Streams   ┌─────────────┐
│ Parquet      │◄─────────│   engine/ (Nautilus)      │──────────────────►│   Redis     │
│ DataCatalog  │  寫/讀    │  • BacktestNode           │  bars/orders/     │  (streams + │
│ (行情/特徵)  │─────────►│  • TradingNode (live)     │  positions/pnl    │   cache)    │
└──────────────┘          │  • Strategy (載入權重推論) │                   └──────┬──────┘
       ▲                  │  • Actor (另類資料/特徵)   │                          │ XREADGROUP
       │ ingest           │  • adapters: Binance...    │                          ▼
┌──────┴───────┐          └──────────────────────────┘                   ┌─────────────┐
│ 資料 ingest   │                                                          │  api/        │
│ (行情商/另類) │                          命令 (Redis stream)             │  (FastAPI)   │
└──────────────┘          ◄──────────────────────────────────────────────│  consumer+hub│
                                                                          │  REST + WS   │
       ┌──────────────┐                                                   └──────┬──────┘
       │ Postgres      │◄── 應用資料: 交易日誌/backtest結果/                      │ WS/REST
       │ (app data)    │    策略參數/模型 metadata                              ▼
       └──────────────┘                                                  ┌─────────────┐
                                                                         │  web/ (Vue3) │
                                                                         │  K線+標記    │
                                                                         │  部位/PnL/控制│
                                                                         └─────────────┘
```

## 2. 各層職責

### 2.1 `engine/` — Nautilus 交易引擎
- 封裝 BacktestNode 與 TradingNode,共用同一份策略碼。
- **Strategy**:事件 handler,載入訓練好的模型權重做推論並下單(含 bracket OTO 進場→TP/SL)。
- **Actor**:餵入另類/自訂資料(衛星、情緒)、計算共用特徵並 `publish_data`。
- **Adapters**:第一期鎖定加密 CEX(Binance/Bybit,data+exec 齊全)。
- 設定 `MessageBusConfig(database=Redis)` 對外串流;`types_filter` 排除高頻 tick。
- 對外接收命令:消費一條 Redis command stream(start/stop/調參/kill switch)。

### 2.2 `research/` — DL/RL 訓練(GPU)
- **特徵管線**:直接讀 ParquetDataCatalog 底層 Parquet → Polars/pandas → 特徵/標籤。特徵碼與引擎 Actor **共用**避免 train/serve skew。
- **RL**:採 **Option D + A**(見 ml-rl 研究)。獨立 Gym 環境訓練(Stable-Baselines3 / RLlib 待定),Nautilus 當高擬真 backtest + live 部署層。必要時用 Option-B thread-handoff 對 Nautilus 微調(後期、原型先行)。
- **DL**:監督式訊號模型(transformer/CNN/LSTM,待定),同樣離線訓練輸出權重。
- 輸出 TorchScript/ONNX 權重 + metadata 進 model store;實驗追蹤待定(MLflow)。

### 2.3 `api/` — FastAPI 後端
- `nautilus_consumer` task `XREADGROUP` 讀 Redis Streams → 正規化 → in-process hub。
- REST:歷史 bars、部位/訂單/PnL 查詢、控制(start/stop/調參)。
- WebSocket gateway:多工 channel、連線快照+delta、有界佇列、`last_seq` 補洞、心跳。
- 控制指令寫回 Redis command stream 給引擎。

### 2.4 `web/` — Vue 3 Dashboard
- Vite + TS + Pinia。Lightweight Charts v5 畫 K 線 + priceLine(進場/SL/TP)+ seriesMarkers(交易箭頭)。
- 即時部位/PnL/訂單面板;策略控制台。

### 2.5 資料與狀態儲存
- **ParquetDataCatalog**:Nautilus 原生,存行情 + 自訂/特徵資料,供 backtest 與訓練。
- **Redis**:Nautilus Cache backing(live 狀態持久化)+ MessageBus Streams(對外串流 + 命令)。
- **Postgres**:**我們自己的**應用資料 — 交易日誌、backtest 結果摘要、策略/參數版本、模型登記 metadata、dashboard 查詢。**不**當 Nautilus cache backend(該功能未成熟)。

## 3. Docker Compose 服務拓樸(第一期)

| 服務 | 映像/基底 | 角色 |
|---|---|---|
| `redis` | redis:7(≥6.2) | Cache + Streams |
| `postgres` | postgres:16 | 應用資料 |
| `engine` | 自建(uv + Python 3.12) | Nautilus Backtest/TradingNode |
| `api` | 自建(uv + FastAPI) | REST + WS gateway |
| `web` | node/vite(dev)→ nginx(prod) | Vue dashboard |
| `research` | 自建(CUDA + uv) | GPU 訓練(可選,按需起) |
| (可選) `mlflow` | mlflow | 實驗追蹤 |

GPU:`research` 用 NVIDIA Container Toolkit;live `engine` 預設 CPU 推論(低延遲),重模型走獨立推論服務。

## 4. 關鍵架構決策(摘要,詳見 tech-stack-decisions)

| # | 決策 | 草案立場 |
|---|---|---|
| AD-1 | RL 整合方式 | Option D(獨立 Gym 訓練)+ A(Nautilus 部署),B 後期微調 |
| AD-2 | ZeroMQ | **第一期不引入**;Redis Streams 已足夠 |
| AD-3 | Postgres 角色 | 僅應用資料,不當 Nautilus cache |
| AD-4 | 第一個市場 | 加密(Binance/Bybit)— data+exec 齊、24/7、API 易 |
| AD-5 | 引擎↔外圍 | Redis Streams(資料+命令) |
| AD-6 | 圖表庫 | Lightweight Charts v5(備 klinecharts) |
| AD-7 | Repo 形態 | Monorepo + uv workspace |
| AD-8 | Nautilus 版本 | Pin stable release |

## 5. 分期路線圖(草案)

- **Phase 0 — 地基**:monorepo + uv workspace、docker-compose(redis/postgres)、Nautilus 安裝驗證、catalog 灌一段歷史資料。
- **Phase 1 — Tracer bullet**:一條最簡策略(如 EMA cross)backtest 跑通 → Redis Streams 串流 → FastAPI → Vue 顯示 K 線 + 進出場標記。打通端到端。
- **Phase 2 — Sandbox/Live**:接 Binance sandbox/testnet,TradingNode 跑通,dashboard 控制 start/stop + kill switch。
- **Phase 3 — 研究管線**:特徵管線、backtest 批量、實驗追蹤、模型 store。
- **Phase 4 — DL 訊號**:監督式模型 → 策略推論。
- **Phase 5 — RL**:Gym 環境訓練 → Nautilus 部署;評估 Option-B 微調。
- **Phase 6 — 另類資料**:衛星等自訂資料 Actor + 特徵。

> 路線與分期需 grill 確認,尤其「先求穩定獲利的簡單策略」vs「直接衝 RL」的優先序。
