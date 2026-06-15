# JimQ 儲存庫結構(定案 v1.0)

> 日期:2026-06-16 · 狀態:**定案**(整合 FastAPI boilerplate 決策後)。取代 `20260616-1220-repo-structure.md` 草案。

## 形態:Monorepo + uv workspace(`research` 獨立 venv)

`api/` fork 自 **benavlabs/FastAPI-boilerplate v0.15.0 classic**(剝除 user/tier/auth,見 decisions-confirmed B5)。

```
JimQ/
├── pyproject.toml              # uv workspace root(members: libs/jimq_core, engine, api)
├── uv.lock
├── docker-compose.yml          # redis, postgres, engine, api, web, (research 按需)
├── .env.example
├── docs/
│
├── libs/jimq_core/             # 共用套件
│   └── jimq_core/
│       ├── schemas.py          # 共用 DTO(engine/api 共用)
│       ├── features.py         # ⭐ 共用特徵庫(engine Strategy 與 research env 共用,消除 train/serve skew)
│       └── constants.py
│
├── engine/jimq_engine/         # Nautilus 引擎
│   ├── strategies/             # 每模型一個獨立 Strategy(模型類型無關 plugin)
│   ├── actors/                 # 另類資料 Actor(Phase 6)
│   ├── adapters/               # Binance/Bybit 永續
│   ├── nodes/                  # BacktestNode / TradingNode
│   ├── config/                 # backtest/sandbox/live
│   ├── streaming/              # MessageBus→Redis Streams;消費 command stream
│   └── catalog/                # ingest 與 catalog 工具
│
├── api/                        # fork FastAPI-boilerplate v0.15.0(剝除版)
│   ├── pyproject.toml · alembic.ini · migrations/
│   └── src/app/
│       ├── main.py
│       ├── core/               # KEEP:config(精簡)/setup/logger/db.database/exceptions/utils.cache
│       ├── models/             # 應用資料:strategy / backtest_run / trade_journal / model_registry
│       ├── schemas/ · crud/    # 對應 Pydantic + FastCRUD(沿用 posts 範本)
│       ├── api/v1/             # strategies / backtests / bars / positions / pnl
│       ├── services/           # nautilus_consumer / hub / store / control(JimQ 特有)
│       ├── ws/stream.py        # WebSocket gateway
│       └── middleware/
│       # STRIP: users/posts/tiers/rate_limit/login/logout/security/token_blacklist/
│       #        admin/scripts.create_first_*/ARQ worker
│
├── research/                   # 獨立 venv(CUDA torch)
│   └── jimq_research/
│       ├── data/               # catalog Parquet → Polars 特徵/標籤
│       ├── envs/               # 自訂薄 perp Gym 環境(+ TorchTrade 探勘)
│       ├── models/             # 序列/policy/多模態 — 各自獨立(C8)
│       ├── training/           # SB3 + MLflow
│       └── export/             # → 權重 + metadata 進 model store
│
├── web/src/                    # Vue3(獨立 npm;OpenAPI 生成 TS 型別)
│   ├── components/{chart,panels,controls}/
│   ├── composables/            # useTradeSocket / useChart
│   └── stores/                 # Pinia
│
├── infra/{docker,postgres,redis}/
├── data/                       # gitignore:catalog + models 權重
├── scripts/                    # ingest / bootstrap
└── tests/                      # 跨套件整合測試
```

## 依賴關係

```
libs/jimq_core ◄── engine(策略/Actor/串流)
       ▲       ◄── research(特徵共用、Gym env)
       └────── ◄── api(DTO schema)
web 獨立(OpenAPI → TS 型別對齊 api)
```

## 關鍵設計點

1. **`features.py` 是反 skew 基石** — engine 推論與 research 訓練共用同一特徵碼。
2. **`engine/strategies/` 每模型獨立 Strategy** — 呼應 C8「3 種模型平行不串接」。
3. **api DB CRUD 只放應用資料**;即時行情走 WS(`services/nautilus_consumer` → `hub` → `ws/stream`),歷史走 catalog(`services/store`)。
4. **Redis 隔離**:boilerplate cache 用不同 DB index,與 Nautilus message bus/streams 分開。
5. **research 不入 uv workspace**(CUDA 重依賴),獨立 venv/映像。
