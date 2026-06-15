# JimQ

以 [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) 為基底的量化交易平台。
目標:用量化交易盡可能賺錢 — 支援 live 交易、backtesting、策略開發,並整合 DL/RL 與另類資料。

## 狀態
✅ **Phase 1 tracer bullet 已完成(卡 #2–#10)。** 整條垂直切片打通:ingest 真歷史 →
EMA backtest(Redis Streams)→ FastAPI consumer/REST/WS → Vue3 + Lightweight Charts 顯示
真 K 線 + 進出場 marker + SL/TP price line + 即時 PnL/部位。**一鍵 docker-compose 全棧**。

> 端到端 demo 一步步操作見 **[`docs/RUNBOOK.md`](./docs/RUNBOOK.md)**(從零到看到圖)。
> 真資料截圖佐證:`web/artifacts/real-e2e-dashboard.png`。

## 全棧端到端 demo(一鍵)

只需 Docker(含 compose v2);Python/Node 全在容器內 build。完整步驟與已知限制見
**[`docs/RUNBOOK.md`](./docs/RUNBOOK.md)**。

```bash
docker compose up -d --build redis postgres api web   # 長駐:api:8000、web:8080
docker compose --profile demo run --rm engine         # 一次性:灌真歷史 + 串流 backtest
docker compose restart api                             # 讓 api 接上本次 stream(@latest)
# 開 http://127.0.0.1:8080 看真 K 線 + 進出場 + PnL
```

## 開發者快速開始(本機,不全容器化)

需求:Python 3.12、[uv](https://docs.astral.sh/uv/) 0.11+、Docker(含 compose v2)。

```bash
# 1. 建立 Python 環境(workspace + pin 版 nautilus_trader 1.228.0)
uv sync

# 2. 準備環境變數
cp .env.example .env        # 預設值即可在本機跑;.env 已 gitignore

# 3. 起本機基礎設施(redis 7.4 / postgres 16,localhost-only)
docker compose up -d
# 等兩者 healthcheck 通過:
docker compose ps          # STATUS 應顯示 (healthy)

# 4. Smoke test(import / 版本 / Redis DB index 隔離)
uv run pytest tests/test_smoke.py -q
# 含 docker 健康檢查的完整 smoke test:
RUN_DOCKER_SMOKE=1 uv run pytest tests/test_smoke.py -q

# 5. 收尾
docker compose down        # 停服務(資料保留於 named volume)
```

### 服務與埠(均綁 localhost)
| 服務 | 映像 | 埠 | 用途 |
|---|---|---|---|
| redis | redis:7.4-alpine | 6379 | Nautilus message bus/streams(DB 0)+ app cache(DB 1,隔離) |
| postgres | postgres:16-alpine | 5432 | 應用資料(交易日誌 / backtest / model registry) |
| api | `infra/docker/api` | 8000 | FastAPI:`alembic upgrade head` → uvicorn;REST `/api/v1/bars`、WS `/ws/stream` |
| web | `infra/docker/web` | 8080 | nginx 伺服 Vue3 build + 反代 `/api`、`/ws` 到 api |
| engine(profile `demo`) | `infra/docker/engine` | — | 一次性 job:ingest 真歷史 + 串流 EMA backtest |

> Redis DB index 隔離契約見 `libs/jimq_core/jimq_core/constants.py`(`REDIS_BUS_DB=0`、`REDIS_CACHE_DB=1`)與 `.env.example`。

## 舊狀態(設計階段)
研究與架構草案已完成,決策已拍板。

## 規劃技術棧
- **引擎**:NautilusTrader(Rust 核心 + Python),uv 管理,Docker 部署
- **狀態/串流**:Redis(Cache + MessageBus Streams)
- **應用資料**:PostgreSQL
- **後端**:FastAPI(REST + WebSocket gateway)
- **前端**:Vue 3 + Vite + TS + Pinia + Lightweight Charts(K 線視覺化)
- **研究**:PyTorch + Gym/RL(GPU)

## 文件
所有研究、架構與決策見 **[`docs/`](./docs/)**。從 [`docs/README.md`](./docs/README.md) 開始。

⚠️ 待決策清單:**[`docs/decisions-to-grill.md`](./docs/decisions-to-grill.md)**(設計給 `/grill-me`)。
