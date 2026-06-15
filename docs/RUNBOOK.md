# JimQ Phase 1 — 端到端 Demo Runbook(卡 #10)

從零到在瀏覽器看到 **真實 BTCUSDT-PERP K 線 + 由真 backtest order/fill 事件驅動的
進場 marker / SL·TP price line / 即時 PnL·部位**。整套以 `docker-compose` 跑,
redis / postgres / api / web 為長駐服務,engine 為一次性 demo job。

> 真相來源:`docker-compose.yml`、`infra/docker/`、`DEV_CONTRACT_AFK.md`。
> 本 demo 完全跑在**本機本棧**(同 compose 網路;鐵律 4/5),不連任何遠端 DB。

---

## 0. 前置需求

| 項目 | 版本 / 說明 |
|---|---|
| Docker + compose v2 | 免 sudo 可用 |
| 外網(選用) | engine demo 從 **Binance public REST** 抓真歷史(免 API key)。無外網時自動 fallback 合成資料,或設 `JIMQ_SYNTHETIC=1` 明確指定 |
| Port | `8000`(api)、`8080`(web)、`6379`(redis)、`5432`(postgres);皆 `127.0.0.1` binding |

無需本機裝 Python / Node / uv / npm —— 全部在容器內 build。

---

## 1. 一鍵起棧(redis / postgres / api / web)

```bash
cd /home/jacc/projects/JimQ

# 首次會 build api/web 映像(uv sync + npm build),約數分鐘。
docker compose up -d --build redis postgres api web
```

啟動序(自動):
- `postgres` / `redis` healthcheck 通過後 `api` 才起。
- `api` entrypoint:等 postgres ready → **`alembic upgrade head`**(鐵律 2:只跑手寫
  migration,絕不 autogenerate / 直接 DDL）→ `uvicorn`。
- `web`:nginx 伺服 `vite build` 產物,反代 `/api`、`/ws` 到 `api`(同源契約,
  前端不需改 base URL)。

驗證服務健康:

```bash
curl -s http://127.0.0.1:8000/health        # {"status":"ok",...}
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/   # 200
```

此時前端已可開(`http://127.0.0.1:8080`),但 catalog 還沒資料、stream 還沒事件,
圖是空的 —— 下一步灌真資料。

---

## 2. 灌真資料 + 跑串流 backtest(engine 一次性 job)

```bash
# 真 BTCUSDT-PERP 1m 歷史(預設 2024-01-01..2024-01-02)→ 啟用 Redis Streams 的 EMA backtest。
docker compose --profile demo run --rm engine
```

engine demo job(`infra/docker/engine/run-demo.sh`)依序:
1. **flush bus DB0**(本棧 demo 獨佔)→ 乾淨可重現。
2. **ingest**:Binance public REST 抓 1m klines → `ParquetDataCatalog`(共享 volume
   `catalog-data`,api 的 `GET /api/v1/bars` 讀同一份)。約 1441 根 bars。
3. **streaming backtest**:`scripts/run_streaming_backtest.py --keep --publish-key`
   —— 跑啟用 Redis Streams 外部串流的 EMA 交叉策略,把 Bar / OrderInitialized /
   OrderFilled / PositionOpened·Closed / AccountState 等事件序列化(msgpack)落地
   **bus DB0**(約 5800+ 筆),並把實際 stream key 寫到已知 key
   `jimq:latest_stream_key`(供 api `@latest` 解析)。

> #5 的 Nautilus Redis 寫入走 Rust MPSC 非同步 flush;腳本會等 stream 落地
>(`XLEN > 0`)才結束,確保 consumer 有完整 backlog 可消費。

常用覆寫:

```bash
# 不同區間 / EMA 週期：
INGEST_START=2024-02-01 INGEST_END=2024-02-02 EMA_FAST=5 EMA_SLOW=13 \
  docker compose --profile demo run --rm engine

# 離線(無外網)合成黃金交叉：
JIMQ_SYNTHETIC=1 docker compose --profile demo run --rm engine
```

---

## 3. 讓 api 接上這次的 stream(restart 一次)

api 在啟動時解析 `JIMQ_STREAM_KEY=@latest`(讀 `jimq:latest_stream_key`)。因為
engine 在 api 起來**之後**才寫入 key,需讓 api 重新解析一次:

```bash
docker compose restart api
```

restart 後 api 的 consumer 會：在 bus DB0 上對這次的 stream key 建 consumer group →
**先排空整段 backlog（id=0）再轉 live（`>`）**→ normalize → publish 到 in-process
hub。WS gateway 連上時送 snapshot(近 500 bars + 最新 orders/fills/position/pnl)→
`{type:live}` → 後續 delta。

驗證 REST 真歷史:

```bash
curl -s "http://127.0.0.1:8000/api/v1/bars?symbol=BTCUSDT-PERP.BINANCE&timeframe=1m" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("bars=",len(d),"first=",d[0])'
# bars= 1441 first= {... 'close': '42331.9' ...}   ← 真 Binance 價
```

---

## 4. 看儀表板

瀏覽器開 **http://127.0.0.1:8080**:

- 真 **BTCUSDT-PERP 1m K 線**(REST 歷史畫初始,WS snapshot 補近 500 根)。
- 由真 order/fill 事件驅動的**進場 marker(箭頭)+ SL/TP price line(水平線)**。
- **即時 PnL / 部位**面板(真 AccountState / Position 事件)。
- 連線狀態 `live`。

### 截圖佐證(對真運行全棧,非 mock)

```bash
cd web && WEB_URL=http://127.0.0.1:8080 node scripts/shoot-real-stack.mjs
# → web/artifacts/real-e2e-dashboard.png
```

交付證據:`web/artifacts/real-e2e-dashboard.png`(真 K 線 + 進出場 + PnL）。

---

## 5. 收棧

```bash
docker compose down            # 停服務,保留資料 volume
docker compose down -v         # 連 volume(catalog/redis/postgres 資料)一起清
```

---

## 一鍵腳本(2→3 合併)

```bash
docker compose up -d --build redis postgres api web
docker compose --profile demo run --rm engine
docker compose restart api
# 開 http://127.0.0.1:8080
```

---

## 架構(本卡接好的整條 tracer bullet)

```
engine(一次性 job)
  ingest_binance.py ─→ ParquetDataCatalog(catalog-data volume)─┐
  run_streaming_backtest.py ─(Nautilus MessageBus, msgpack)─┐   │
                                                            ▼   │
                                      Redis Streams bus(DB0)   │ 共享 catalog
                                  + jimq:latest_stream_key      │
                                                            │   │
api(長駐)                                                  ▼   ▼
  lifespan @latest 解析 → consumer(排空 backlog→live)→ in-process hub
  GET /api/v1/bars ──(REST 真歷史)──────────────────────────────┐
  WS /ws/stream  ──(snapshot+delta:bars/orders/fills/positions/pnl)─┐
                                                                  │ │
web(長駐,nginx 反代 /api、/ws → api)                            ▼ ▼
  Vue3 + Lightweight Charts v5:K 線 + marker + priceLine + PnL/部位
```

環境變數覆寫(compose 內用服務名;本機開發維持 localhost 預設):
`REDIS_HOST` / `REDIS_PORT`(bus DB0、cache DB1)、`POSTGRES_HOST` / `POSTGRES_PORT`、
`JIMQ_STREAM_KEY`(`@latest` 或字面 key)、`JIMQ_CATALOG_PATH`。

---

## 已知限制 / 下一步(Phase 2)

**已知限制(Phase 1 tracer bullet 範圍內,符合預期):**

- **Demo 是 backtest replay,非即時行情**:engine 為一次性 job,事件一次寫滿 stream;
  api 排空 backlog 後以 snapshot 一次呈現,沒有「逐根動畫」的 live tick。要看 live
  逐筆 replay 需 Phase 2 的串流節流 / 重播器。
- **api 需在 engine 之後 restart 一次**才解析到本次 stream key(`@latest` 在啟動時
  解析)。可接受的 demo 步驟;Phase 2 可改成 api 監聽 `latest_stream_key` 變更熱重載
  consumer,免 restart。
- **orders 面板**只反映 snapshot 當下的開放單;歷史進出場以**圖上 marker/priceLine**
  呈現(訂單表非完整成交日誌)。完整 trade journal(postgres)是 Phase 2。
- **無 auth / 多使用者 / 多 instrument**:單一 BTCUSDT-PERP、單 trader,前端硬編
  symbol/timeframe(decisions-confirmed 範圍)。
- **backtest 結果未落 postgres**:`backtest_run` 表與 migration 已就緒(`alembic
  upgrade head` 會建),但本 demo 的事件流走 Redis,不寫 DB。
- **web build 用 `build:nocheck`**(容器內跳過 vue-tsc 型別檢查避免版本差異卡關);
  型別檢查仍由本機 / CI `npm run build` 把關(#9 已綠)。

**Phase 2 方向:**

- **sandbox / live 接線**:`streaming_message_bus_config()` 已設計為 backtest + live
  TradingNode 共用;接 Binance testnet/live adapter,同一條 consumer→hub→WS 不變。
- **live 串流節流 / 重播器**:逐根推送、可調速重播,前端動畫化。
- **trade journal + 回測註冊**:成交 / 部位 / 回測結果落 postgres(`backtest_run` 已
  備),前端歷史查詢。
- **api 熱重載 consumer**:監聽 `latest_stream_key` 免 restart;多 stream / 多策略。
- **觀測性 / CI**:compose healthcheck smoke(`tests/test_smoke.py`,`RUN_DOCKER_SMOKE=1`)
  納入 CI;前端 `shoot-real-stack.mjs` 當 e2e 煙霧測試。
```
