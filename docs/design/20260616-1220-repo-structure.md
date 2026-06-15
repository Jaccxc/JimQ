# JimQ 儲存庫結構(草案 v0.1)

> 日期:2026-06-16 · 狀態:**草案,待 `/grill-me` 確認** · 尚未建立任何程式碼,僅規劃。

## 形態:Monorepo + uv workspace

```
JimQ/
├── pyproject.toml              # uv workspace root(members: engine, research, api, libs)
├── uv.lock
├── docker-compose.yml          # redis / postgres / engine / api / web / research
├── .env.example                # 連線設定範本
├── README.md
│
├── docs/                       # 所有設計與決策文件(時間戳命名)
│   ├── research/               # 外部研究整理
│   └── design/                 # 架構與決策
│
├── libs/                       # 共用 Python 套件(型別/schema/常數)
│   └── jimq_core/
│       ├── pyproject.toml
│       └── jimq_core/
│           ├── schemas.py      # Pydantic DTO(bars/orders/positions/命令信封)
│           ├── features.py     # 共用特徵碼(引擎 Actor 與 research 共用,避免 skew)
│           └── constants.py
│
├── engine/                     # Nautilus 交易引擎
│   ├── pyproject.toml          # 依賴 nautilus_trader, jimq_core
│   └── jimq_engine/
│       ├── strategies/         # Strategy(載入權重推論、bracket 進出場)
│       ├── actors/             # 另類資料/特徵 Actor
│       ├── adapters/           # venue 設定(Binance/Bybit...)
│       ├── nodes/              # BacktestNode / TradingNode 組裝
│       ├── config/             # 各環境設定(backtest/sandbox/live)
│       ├── streaming/          # MessageBus → Redis Streams 設定;命令 stream 消費
│       └── catalog/            # 資料 ingest 與 catalog 寫入/查詢工具
│
├── research/                   # DL/RL 訓練(GPU,可能獨立環境)
│   ├── pyproject.toml          # torch, gymnasium, sb3/rllib, mlflow, jimq_core
│   └── jimq_research/
│       ├── data/               # 從 Parquet catalog 讀 → Polars 特徵/標籤
│       ├── envs/               # Gym 環境(RL 訓練;Option-B Nautilus 橋接原型)
│       ├── models/             # 模型定義(transformer/CNN/LSTM/policy net)
│       ├── training/           # 訓練迴圈、超參、實驗追蹤
│       └── export/             # → TorchScript/ONNX + metadata 進 model store
│
├── api/                        # FastAPI 後端
│   ├── pyproject.toml          # fastapi, uvicorn, redis, asyncpg, jimq_core
│   └── jimq_api/
│       ├── main.py             # app + lifespan(consumer/broadcaster task)
│       ├── routes/             # bars / positions / orders / pnl / control
│       ├── ws/                 # WebSocket gateway(多工、快照+delta、心跳)
│       └── services/           # nautilus_consumer / hub / store / control
│
├── web/                        # Vue 3 dashboard(獨立 npm 專案)
│   ├── package.json            # vite, vue3, typescript, pinia, lightweight-charts
│   ├── vite.config.ts
│   └── src/
│       ├── components/chart/   # CandleChart / PriceLines / TradeMarkers
│       ├── components/panels/  # PositionsTable / OrdersTable / PnlWidget
│       ├── components/controls/# StrategyControls
│       ├── composables/        # useTradeSocket / useChart
│       └── stores/             # Pinia: market/positions/orders/pnl/connection/strategy
│
├── infra/                      # 基礎設施
│   ├── docker/                 # 各服務 Dockerfile
│   ├── postgres/               # 初始 schema / migration
│   └── redis/                  # redis 設定
│
├── data/                       # 本地資料(gitignore)
│   ├── catalog/                # ParquetDataCatalog 根(NAUTILUS_PATH)
│   └── models/                 # 訓練輸出權重(model store)
│
├── scripts/                    # 一次性工具(ingest 歷史資料、bootstrap DB)
└── tests/                      # 跨套件整合測試(各套件另有單元測試)
```

## 套件依賴關係

```
libs/jimq_core  ◄── engine     (策略、Actor、串流)
       ▲        ◄── research    (特徵共用、Gym 環境)
       └─────── ◄── api         (DTO schema)
web  獨立(透過 OpenAPI 生成 TS 型別與 api 對齊)
```

## uv workspace 草案

root `pyproject.toml`:
```toml
[tool.uv.workspace]
members = ["libs/jimq_core", "engine", "research", "api"]
```
- 單一 `uv.lock`,各套件 `pyproject.toml` 宣告自身依賴。
- ⚠️ **待確認**:`research`(CUDA torch)依賴重,是否拆出 workspace 用獨立 venv(避免拖累 engine/api 的解析與映像體積)?見 tech-stack AD-7。

## .gitignore 要點

- `data/`(catalog 與權重,大檔)、`.env`、`__pycache__`、`web/node_modules`、`web/dist`、`.venv`、`uv` 快取、模型 checkpoint。

## 待確認(grill)

1. `research` 是否拆出獨立環境(CUDA 重依賴)?
2. `web` 放 monorepo 內還是獨立 repo?(建議內,OpenAPI 生成型別對齊)
3. 大型資料/權重用 git-lfs、DVC,還是純本地 + 物件儲存(S3/MinIO)?
4. 命名:`jimq_*` 套件前綴可接受嗎?
