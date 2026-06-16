# JimQ — Binance testnet live 資料節點 Runbook(卡 #27 / P2-S1)

從零到在 **Live 頁**看到 Binance USDT-M Futures **testnet** 的真即時 BTCUSDT-PERP K 線。

> 真相來源:`docs/research/20260616-nautilus-infra.md`(Binance adapter/testnet/
> 外部串流)、`docs/design/20260616-1830-decisions-confirmed.md`、`DEV_CONTRACT_AFK.md`。
> 復用 Phase 1 串流脊椎(#5 streaming MessageBus → Redis Streams → #7 consumer →
> WS gateway → 前端 chart)。
>
> ⛔ **本節點只接 read-only 市場資料,不下任何單**(下單在 P2-S2/S3)。
> 🔑 **金鑰只從 `.env.afk` 的 `BINANCE_TESTNET_KEY` / `BINANCE_TESTNET_SECRET` 讀,
> 絕不 commit。** 連 Binance testnet 需外網(屬外部 venue 資料來源,鐵律 4 允許)。

---

## 0. 前置需求

| 項目 | 說明 |
|---|---|
| Redis | 本機 docker-compose（localhost:6379；bus = DB0） |
| Postgres | 本機 docker-compose（API 應用資料；live 節點本身不需要） |
| 金鑰 | `.env.afk` 內 `BINANCE_TESTNET_KEY` / `BINANCE_TESTNET_SECRET`（HMAC-SHA-256） |
| 外網 | 能連 `https://testnet.binancefuture.com`（live 資料節點訂閱所需） |

申請 testnet 金鑰:https://testnet.binancefuture.com → 登入 → 產生 API key
（USDT-M Futures testnet；需勾選 **Enable Futures**；若帳戶設了 IP 白名單，
務必把本機出口 IP 加入，否則簽章請求回 `-2015 Invalid API-key, IP, or permissions`）。

---

## 1. 起 live 資料節點

```bash
uv run python scripts/run_live_data.py
```

行為:
1. 載 `.env.afk` 金鑰（`credentials_from_env`；缺則 raise，無硬編 default）。
2. 用 `BinanceLiveDataClientFactory` 建 **testnet / USDT_FUTURES / HMAC** data client，
   無 exec client（不下單）。
3. 掛 `streaming_message_bus_config()`（#5）→ 事件序列化（msgpack）落地本機
   Redis Streams（DB0），`types_filter` 排 QuoteTick/TradeTick 高頻 tick。
4. `BarSubscriberActor` 在 `on_start` 訂閱 `BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL`。
5. 把實際事件 stream key 寫到 `jimq:latest_stream_key`（供 API `@latest` 解析、前端訂閱）。
6. Ctrl-C / SIGTERM 優雅停止並清掉 published key。

可選旗標:`--bar-spec 1-MINUTE-LAST-EXTERNAL`、`--no-publish-key`。

外部觀察事件落地:
```bash
redis-cli -n 0 GET jimq:latest_stream_key
redis-cli -n 0 XLEN "<上面那個 key>"
redis-cli -n 0 XRANGE "<key>" - + COUNT 5
```

---

## 2. 起 API（consumer + WS gateway）

API 在 `JIMQ_STREAM_KEY=@latest` 時從 `jimq:latest_stream_key` 解析 live 節點的 key，
`run_consumer` 以 XREADGROUP 讀 Redis Streams DB0，normalize 後 publish 到 hub，
WS `/ws/stream` 推給瀏覽器。`data.bars.` topic → `bars` channel。

```bash
JIMQ_STREAM_KEY=@latest uv run uvicorn app.main:app --app-dir api/src --port 8000
```

---

## 3. 起前端，看 Live 頁

```bash
cd web && npm run dev
```

開瀏覽器到 `/`（自動重導向 `/live`）。tabbed shell：
- header nav **[Live] [Backtest] [Research]** + **mode badge**（live 節點在跑 = `LIVE-TESTNET`）
  + 全域 **KILL**（本卡 disabled placeholder，真功能待 P2-S3）+ WS 狀態。
- **Live 頁**:即時 K 線（CandleChart/ChartController + useTradeSocket）顯示真即時
  BTCUSDT-PERP + symbol/timeframe 選擇器 + EMA（W3）。部位/PnL 面板為佔位（下單 P2-S2）。

---

## 4. 測試

```bash
# 後端單元（節點組裝 / 不連網路）
uv run pytest engine/tests/test_live_node.py -q

# 後端真 testnet 整合（gated;需外網 + 有效金鑰 + 本機 Redis）
JIMQ_RUN_TESTNET=1 uv run pytest engine/tests/test_live_node_testnet.py -q

# 前端
cd web && npm run test && npm run build && node scripts/verify-p2s1.mjs
```

---

## 5. 疑難排解

| 症狀 | 原因 / 處置 |
|---|---|
| `-2015 Invalid API-key, IP, or permissions` | testnet 金鑰無效 / 過期 / IP 白名單未含本機出口 IP / 未啟用 Futures。到 testnet 後台重產金鑰並加 IP。 |
| Live 頁 badge 顯示但圖無資料 | 確認 `run_live_data.py` 在跑、`jimq:latest_stream_key` 有值、API 以 `@latest` 啟動、XLEN 增長。 |
| WS 狀態卡 connecting | API 未起或 stream key 解析不到;檢查 consumer log。 |

---

## 6. 已知限制 / 待人眼複核

- **本卡撰寫時 `.env.afk` 內的 testnet 金鑰被 Binance 以 `-2015` 拒絕**（已直接以簽章
  REST `/fapi/v2/account` 驗證:public endpoint 200,signed 回 401 `-2015`）。
  串流脊椎已驗證可用(節點連上 testnet、`ComponentStateChanged` 等事件成功落地 Redis
  Streams DB0),但**真 authenticated 即時 bar 未取得**,需有效金鑰 / 正確 IP 白名單後
  重跑 `JIMQ_RUN_TESTNET=1` 整合測試確認 bar 落地。
- Binance Futures 公開市場資料(K 線 WS)本身不需簽章;若僅要無金鑰公開行情,後續可
  評估改 instrument provider 走純 public 載入路徑(本卡未做,維持 adapter 預設)。

---

## 7. paper 下單的風控 / kill / 對帳(卡 #29 / P2-S3)

`scripts/run_live_trade.py` 在 testnet paper 下單時掛 Nautilus 原生 `LiveRiskEngineConfig`:

- `--max-notional`(預設 **200 USDT**)= `max_notional_per_order`。**⚠️ 上游限制**:
  nautilus_trader 1.228 名目風控對 **MARGIN 帳戶 early-return**(原碼 "TODO: risk controls
  for margin"),Binance USDT-M Futures = MARGIN → 名目上限**目前期貨 testnet 上不觸發
  OrderDenied**;config 欄位已 forward-compatible 掛好,Nautilus 補上即生效。名目攔截
  真行為已用 spot+CASH backtest 確定性驗(`engine/tests/test_risk_engine_deny.py`)。
- `--max-order-submit-rate`(預設 **10/00:00:01** = 10 單/秒)= `max_order_submit_rate`
  throttler,**所有帳戶型別生效**(含期貨)。超頻被節流。`bypass=False` 不可繞過。
- **Kill switch**:web header 全域 KILL(或 `POST /api/v1/kill`)→ command stream → engine
  worker → `NodeController.kill()`,每策略依序 **cancel_all_orders(撤未成交)→
  close_all_positions(平倉)→ stop**,節點標記 KILLED。不留掛單在 venue。
- **對帳**:`LiveExecEngineConfig.reconciliation=True`(預設開),節點重啟與 venue 對齊
  既有部位/掛單(以 `strategy_id=EXTERNAL` 重發事件)。

控制列(`StrategyControls`)顯示節點狀態徽章(RUNNING/KILLED)+ 生效中風控摘要。
