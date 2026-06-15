# JimQ 決策定案(grill 後)

> 日期:2026-06-16 · 狀態:**已定案**(經 `/grill-me` 逐題確認)。本文為權威來源,取代 `decisions-to-grill.md` 與先前草案中對應條目的「立場」。

## 戰略層

| # | 決策 | 定案 |
|---|---|---|
| A1 | 第一個市場 | **加密貨幣**先行,**之後加 FX**。加密用 **Binance/Bybit** |
| A1b | 現貨/合約 | **永續合約**(可多空、有槓桿;與 FX 做空特性一致) |
| A2 | 交易頻率 | **Intraday~Swing(分鐘~小時)**,bar 級資料即可,非 HFT |
| A3 | 優先序 | **先打通簡單策略全鏈**(tracer bullet:backtest→sandbox→live + dashboard),再疊 RL |
| A4 | 資金/真錢 | **先 testnet/paper**,通過 sandbox + 風控後**小額真錢**驗證 |

## 架構層

| # | 決策 | 定案 |
|---|---|---|
| B1 | RL 整合路線 | **Option D+A**:獨立 Gym 環境訓練 + Nautilus 當高擬真 backtest/live 部署層;Option-B(thread-handoff)僅後期微調原型 |
| B1b | RL 訓練 stack | **主線:Stable-Baselines3 + 自訂薄 perp Gym 環境**(observation/reward/特徵與 Nautilus Strategy **共用**,消除 train/serve skew)。**探勘軌:TorchTrade**(原生 perp,Phase 5 原型評估)。FinRL/TensorTrade 僅當參考,不當依賴 |
| B2 | ZeroMQ | **第一期不引入**,只用 Redis Streams(有持久化/重播)。日後需要再加 relay |
| B3 | Postgres 角色 | **僅應用資料**(交易日誌/backtest 結果/策略參數/模型 metadata),**位在 FastAPI 後端那層**。不當 Nautilus cache(用 Redis) |
| B4 | 命令路徑 | **第二條 Redis command stream**,Nautilus 節點內 command Actor 消費(解耦、可重播、可審計) |

## 技術棧

| # | 決策 | 定案 |
|---|---|---|
| C2 | research 環境 | **拆出獨立 venv/映像**(CUDA torch 重依賴),不拖累 engine/api |
| C3 | Nautilus 版本 | **pin stable PyPI wheel**(免編 Rust) |
| C4 | Python 版本 | **3.12** |
| C5 | 圖表庫 | **Lightweight Charts v5**(接受 TradingView 標註) |
| C6 | 歷史資料 | **交易所免費 bar/成交 + funding rate**(Binance/Bybit)灌 catalog |
| C9 | 另類資料 | **自訂資料 Actor → 特徵**,排 **Phase 6(最後)** |
| C10 | 資料/權重版本 | **純本地(gitignore)+ 之後 MinIO/S3**;模型用簡單 model store + Postgres metadata |

## ⭐ C8 — 模型願景(關鍵,已澄清)

使用者要的 3 種模型是**各自獨立、平行存在、服務不同任務,彼此不串接**:
1. **RL policy**(狀態→動作)— B1 主線
2. **序列模型**(Transformer/LSTM on bars+特徵)— 預測方向/波動
3. **多模態/另類資料融合模型** — Phase 6 起

**架構含意**:research 層與 engine 層必須做成**模型類型無關的可插拔架構**:
- 每種模型獨立訓練 → 輸出自己的權重 artifact。
- 每個權重對應**一個獨立的 Nautilus Strategy**(各自的特徵/observation 建構)。
- **不**設計成單一「encoder→embedding→policy」融合管線。
- 共用的是**基礎設施**(特徵庫 `libs/jimq_core`、catalog、model store、串流),不是模型本身。

## 對先前草案的修訂

- `architecture-overview` 的「模型層」描述需從「encoder→policy 融合」改為「**多個平行獨立模型軌**,各對應獨立 Strategy」。
- `tech-stack-decisions` AD-1/AD-11 以本文 B1/B1b 為準(SB3 + 自訂 env 主線、TorchTrade 探勘)。
- ZeroMQ(AD-2)、Postgres(AD-3)、市場(AD-4)、頻率(AD-13)等均依本文定案。

## B5 — FastAPI 後端基底(2026-06-16 追加定案)

- **Fork `benavlabs/FastAPI-boilerplate` 的 v0.15.0 classic**(`src/app/` 佈局,MIT)。理由:佈局符合預期、auth 耦合最少、`posts` 模組可當交易模組範本。
- **KEEP**:async SQLAlchemy 2.0、`core/config.py`(精簡)、`core/setup.py`(去 superuser docs gate)、`core/utils/cache.py`、exceptions、middleware、FastCRUD 模式、Alembic、docker-compose 的 db+redis+web。
- **STRIP**:users / posts / tiers / rate_limit / login / logout / `core/security.py` / token_blacklist / admin(crudadmin)/ `scripts.create_first_*` / auth deps / Crypt+FirstUser+CRUDAdmin settings mixin。
- **移除 ARQ worker**(Nautilus 才是 bus/worker)。rate-limiter 依賴 user/tier → 改 flat IP 級或移除。
- **Redis 隔離**:cache 用**不同 DB index/實例**,與 Nautilus message bus/streams 分開。
- **新 CRUD 模組(應用資料)**:`strategy` / `backtest_run` / `trade_journal` / `model_registry`(皆無 user FK)。**注意**:bars/orders/positions/pnl **主要走 WS 串流 + catalog 歷史查詢,非 DB CRUD**。
- 完整結構見 `docs/design/20260616-1845-repo-structure-final.md`。

## 下一步:Phase 0 地基(待你指示開工)

1. monorepo + uv workspace(`libs/jimq_core`、`engine`、`api`;`research` 獨立 venv)
2. docker-compose:redis + postgres
3. 安裝 pin 版 Nautilus(Python 3.12)並驗證
4. 寫歷史資料 ingest 腳本(Binance/Bybit klines+funding)→ ParquetDataCatalog
5. 準備 Phase 1 tracer bullet 的最簡策略骨架
