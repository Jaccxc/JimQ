# JimQ — 啟動總指南(Quickstart)

> 一份搞定「怎麼啟動」。四種使用模式,從零到看到畫面。
> 寫於 2026-06-16,涵蓋 Phase 1(回測)、Phase 2(testnet 真即時 + paper 下單)、
> Phase 3(研究)、Phase 4(operator console)全部已完成功能。

打開瀏覽器都是同一個 operator console(頂部分頁 **[Live] [Backtest] [Research]**),
差別只在你**背後跑哪個引擎**。下面四節對應四個目的。

---

## 0. 共用前置(每種模式都要先做)

需求:Docker(含 compose v2)、Python 3.12、[uv](https://docs.astral.sh/uv/) 0.11+、Node 18+。

```bash
cd /home/jacc/projects/JimQ

# 1. Python 環境(workspace + pin 版 nautilus_trader 1.228.0)
uv sync

# 2. 起本機基礎設施(redis 7.4 / postgres 16,均綁 localhost)
docker compose up -d redis postgres
docker compose ps                      # 兩者 STATUS 應為 (healthy)

# 3.(首次)套 DB schema
cd api/src && uv run alembic upgrade head && cd ../..
```

> 金鑰:Phase 2(模式 B/C)需要 `.env.afk` 內 `BINANCE_TESTNET_KEY` / `BINANCE_TESTNET_SECRET`
> (USDT-M Futures **testnet**,絕不 commit)。已備妥。

---

## 模式 A — 回測 demo(最快,不需金鑰,一鍵 docker)

只想看「真歷史資料 → EMA 回測 → K 線 + 進出場 marker」整條打通:

```bash
docker compose up -d --build redis postgres api web   # 長駐:api:8000、web:8080
docker compose --profile demo run --rm engine         # 一次性:灌真歷史 + 串流 backtest
docker compose restart api                             # 讓 api 接上本次 stream(@latest)
# 開 http://127.0.0.1:8080 → Backtest 頁
```

也可在 **web 的 Backtest 頁直接用表單跑**(symbol/tf/strategy/參數/日期 → Run),
中間圖會即時長出,下方 History 表可重載過往 run。(Phase 4 W1/W2 功能)

---

## 模式 B — 看 Binance testnet 真即時 K 線(read-only,不下單)

想在 **Live 頁**看真實市場即時跳動的 BTCUSDT-PERP,但不下任何單:

開三個終端(或用 `&` 背景跑):

```bash
# 終端 1 — live 資料節點(連 testnet,真即時 1m bar → Redis Streams DB0)
uv run python scripts/run_live_data.py

# 終端 2 — API(consumer + WS gateway;@latest 自動解析 live 節點的 stream key)
JIMQ_STREAM_KEY=@latest uv run uvicorn app.main:app --app-dir api/src --port 8000

# 終端 3 — 前端
cd web && npm install && npm run dev
```

開瀏覽器 → 自動到 `/live`。mode badge 顯示 **LIVE-TESTNET**,圖即時跳動。
部位/PnL 面板此模式為佔位(沒下單)。

驗證資料真的有進來:
```bash
redis-cli -n 0 GET jimq:latest_stream_key
redis-cli -n 0 XLEN "$(redis-cli -n 0 GET jimq:latest_stream_key)"   # 應持續增長
```

---

## 模式 C — testnet paper 下單(⛔ 假錢,真在 testnet 成交)

想看策略**真的下單 → 成交 → 部位 → PnL** 在 Live 頁面板跳出來
(這是目前最完整的 live 體驗):

跟模式 B 一樣,只是把**終端 1 換成交易節點**:

```bash
# 終端 1 — live 交易節點(data + exec,ema_cross 在即時 bar 下 0.001 BTC paper 單)
uv run python scripts/run_live_trade.py
#   --fast 3 --slow 8 --trade-size 0.001   # 調策略/單量
#   --duration 180                          # 跑 180s 後自動停(驗 round-trip)

# 終端 2、3 同模式 B(API @latest + web)
```

開 `/live`,等 EMA 交叉觸發後,**Orders / Fills / Positions / PnL 面板**會顯示真 live 值。
近期成交截圖佐證:`web/artifacts/p2s2-paper-trade-live.png`。

> ⛔ 硬性安全:程式碼鎖死 `BinanceEnvironment.TESTNET`,任何非 testnet 設定會被
> `assert_testnet_only` 擋下拋例外。**永遠是假錢,不碰真實資金。**

---

## 模式 D — 研究管線(dataset / 模型 / MLflow)

研究在**獨立 venv**(CUDA torch,與主 workspace 隔離)。詳見
[`docs/runbooks/20260616-research-demo.md`](./20260616-research-demo.md)。
web 的 **Research 頁**可看 model_registry、MLflow runs、觸發 build dataset / train job。

---

## 各模式對照表

| 模式 | 背後引擎指令 | 需金鑰 | 看哪頁 | 會下單? |
|---|---|---|---|---|
| A 回測 | `docker compose --profile demo run engine` | 否 | Backtest | 模擬 |
| B 真即時資料 | `scripts/run_live_data.py` | 是(testnet) | Live | 否 |
| C paper 下單 | `scripts/run_live_trade.py` | 是(testnet) | Live | ⛔ testnet 假錢 |
| D 研究 | research venv(見研究 runbook) | 否 | Research | — |

> 控制平面(從 web 直接 start/stop/kill 引擎節點,免手動開終端)是 Phase 4 W5 +
> P2-S3(#29)的範圍 — live 節點生命週期控制下一步接上。

## 疑難排解

| 症狀 | 處置 |
|---|---|
| `-2015 Invalid API-key` | testnet 金鑰無效/IP 白名單未含本機/未啟用 Futures。到 testnet.binancefuture.com 重產。 |
| Live 頁有 badge 但圖無資料 | 確認終端 1 在跑、`jimq:latest_stream_key` 有值、API 以 `@latest` 啟動、XLEN 增長。 |
| WS 卡 connecting | API 未起或 stream key 解析不到;看 consumer log。 |
| docker 權限 | 見 `DEV_CONTRACT_AFK.md` / 環境記錄(已 `usermod -aG docker`)。 |

相關 runbook:[`20260616-live-data-testnet.md`](./20260616-live-data-testnet.md)(P2-S1 細節)、
[`20260616-research-demo.md`](./20260616-research-demo.md)(研究)、
根目錄 [`README.md`](../../README.md)、[`DEV_CONTRACT_AFK.md`](../../DEV_CONTRACT_AFK.md)。
