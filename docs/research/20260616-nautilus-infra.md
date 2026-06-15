# 研究:NautilusTrader 部署、基礎設施與整合

> 來源:官方 docs + GitHub repo + `nautilus-infrastructure` Rust crate。整理於 2026-06-16。
> 支援基準:Python 3.12–3.14,release 線約 1.2xx。

## 1. Redis

- 用途有二:**Cache database backing**(持久化訂單/部位/帳戶/instrument/市場史,可重啟續跑)、**MessageBus backing**(訊息序列化進 **Redis Streams**,做持久化與對外串流)。
- **可選,非必要**。`CacheConfig.database` 預設 `None`,純記憶體可跑。
- 版本:**Redis 6.2+**(Streams 需要)。
- 設定:共用 `DatabaseConfig(type="redis", host, port, ...)` 傳入 `CacheConfig` 與 `MessageBusConfig`。預設 msgpack。寫入在獨立 Rust 執行緒(MPSC),不阻塞交易執行緒。

## 2. PostgreSQL — 誠實狀態

- **有原生 Postgres 工作,但要小心依賴**:
  - Rust `nautilus-infrastructure` crate 實作了 **PostgreSQL SQL cache database**(feature flag,與 Redis 並列)。源自 issue #1332。
  - 有 **Nautilus CLI** 可 bootstrap/管理 Postgres(schema、連線設定)。
- ⚠️ **注意**:
  - **使用者面向的概念 docs(Cache、Architecture)只記載 Redis**。Postgres 只在 Rust crate 層級有文件。
  - **無法從官方 docs 確認** Postgres cache backend 已像 Redis 那樣透過 Python `DatabaseConfig`/`CacheConfig` 接通並可正式使用。視為**已實作但未成熟 / 文件不全**,主要是 Rust 側仍在成熟的功能。
- **對 JimQ 的建議**:**今天用 Redis 當 cache + message-bus backend**。Postgres 拿來放**我們自己的應用資料**(dashboard、分析、交易日誌、backtest 結果、模型登記),由 Redis Streams 餵入 — 這完全在我們掌控內。

## 3. ZeroMQ / 訊息佇列 — 誠實答案

- **Nautilus 不原生使用 ZeroMQ**。message bus/architecture/config 都零提及。(歷史:很舊的 pre-rewrite 版據說內部用過 ZeroMQ,現在的 Rust-native 架構不用 — 訊息走 in-process `MessageBus` + **Redis Streams** 對外傳輸。)
- **ZeroMQ 在 JimQ 架構的位置(Nautilus 之外)**:Nautilus 對外發佈機制是 Redis Streams,不是通用 broker。所以 ZeroMQ 會在**我們自建的外圍層**:
  - 一個 bridge/relay 服務訂閱 Nautilus Redis Streams,再**用 ZeroMQ 轉發**(PUB/SUB 扇出給 dashboard,PUSH/PULL 分配工作)。
  - 適合**低延遲扇出到前端/WebSocket gateway** 或**解耦微服務**,位在 Nautilus **下游**。
- 無內建 ZeroMQ adapter,要自己寫 glue。**Redis Streams 才是原生接縫。**

> JimQ 判斷:既然 Redis Streams 已能做 engine→dashboard,**ZeroMQ 在第一版可能是多餘的**。是否引入列為待 grill 決策。

## 4. TradingNode(live)部署

```python
from nautilus_trader.adapters.binance import BINANCE, BinanceLiveDataClientFactory, BinanceLiveExecClientFactory
from nautilus_trader.live.node import TradingNode

node = TradingNode(config=config)
node.add_data_client_factory(BINANCE, BinanceLiveDataClientFactory)
node.add_exec_client_factory(BINANCE, BinanceLiveExecClientFactory)
node.build(); node.run()
```
- `TradingNodeConfig`(繼承 `NautilusKernelConfig`)含:`trader_id`、`environment`(LIVE/SANDBOX/BACKTEST)、`logging`、`cache`、`message_bus`、`data_clients`/`exec_clients`(venue→設定 dict)、各引擎設定、timeouts。
- `LiveExecEngineConfig` 預設開啟**對帳**(啟動時與 venue 對齊訂單/部位狀態)。重啟正確性的關鍵。
- **同碼 backtest→live**:策略/exec algo 不變。
- **Docker**:官方**未**規範 TradingNode 的容器部署拓樸。`[docker]` extra 是給 **Interactive Brokers Gateway** 容器用的,不是容器化 Nautilus。→ 我們自寫 Dockerfile(Python 3.12–3.14 base,`uv pip install`),旁掛 Redis(與 Postgres)。

## 5. Adapters / 整合(18 個)

| Venue | 類型 | 狀態 | 備註 |
|---|---|---|---|
| Binance | Crypto CEX | Stable | 現貨+期貨;data+exec |
| Bybit / OKX / Coinbase Intl / BitMEX / Deribit / Kraken | Crypto CEX | Stable | data+exec |
| dYdX / Hyperliquid | Crypto DEX | Stable | data+exec |
| Derive / Lighter | Crypto DEX | Beta | |
| **Interactive Brokers** | 傳統券商(股/選/期/FX/債,多 venue) | Stable | data+exec;需 TWS/Gateway(`[ib]`/`[docker]`) |
| AX Exchange / Betfair / Polymarket | 永續/體育博弈/預測市場 | Stable | data+exec |
| **Databento** | 行情資料商 | Stable | **僅 DATA**(DBN 格式) |
| **Tardis** | crypto 資料商 | Stable | **僅 DATA** |

- 多數 venue 同時提供 data + execution。
- **僅資料**:Databento、Tardis(要交易需配獨立執行 venue)。
- **加密為主**;**傳統資產主要靠 Interactive Brokers**。

## 6. 對外串流(給 live dashboard)

機制 = **MessageBus external streaming via Redis Streams**:
1. 設 `MessageBusConfig(database=DatabaseConfig(...))`,每則發佈訊息序列化(msgpack/json)寫入 Redis Streams。
2. 用欄位調整 stream key:`streams_prefix`、`use_trader_prefix`/`use_trader_id`/`use_instance_id`、`stream_per_topic`(Redis 建議 `False`)、`types_filter`(排除高頻型別)、`autotrim_mins`。預設 key:`trader:{trader_id}:{instance_id}:{streams_prefix}`。
3. **我們的外部服務**(FastAPI + WebSocket)當獨立行程/容器,`XREAD`/`XREADGROUP` 讀 stream,反序列化 Nautilus 型別,推給瀏覽器。

乾淨架構:`TradingNode → Redis Streams →(我們的 relay)→ FastAPI/WebSocket → dashboard`。要 ZeroMQ 就插在 relay 那步。

## 7. Python / Rust build / uv

- **Python:3.12 / 3.13 / 3.14**(僅 64-bit)。
- 平台:Linux(Ubuntu 22.04+,x86_64+ARM64)、macOS 15+、Windows Server 2022+。**Linux/macOS wheel 預設高精度(128-bit);Windows 僅標準精度(64-bit)** → 要 16 位小數請用 Linux。
- 安裝(推薦):**`uv pip install nautilus_trader`**。有 PyPI 預編 wheel,多數人不用編 Rust。
- dev/nightly:`--index-url=https://packages.nautechsystems.io/simple`。
- Extras:`[ib]`、`[docker]`(IB Gateway)、`[betfair]`、`[polymarket]`、`[visualization]`。
- 從原始碼編(僅平台無 wheel 或要 develop):需 Rustup、Clang、uv、Cap'n Proto,`uv sync --all-extras`。
- Nautilus 官方標準化在 **uv**(`uv pip install` 與 `uv sync`)。

## 對 JimQ「production-ish」stack 的結論

- **Redis:用**。是 Cache(狀態持久化)與 MessageBus(Redis Streams = 串流接縫)的原生 backend。6.2+。
- **PostgreSQL:部分支援/成熟中**。Rust 層有 cache backend + CLI,但 Python API 文件不全。依賴前先驗證版本;同時 Postgres 很適合放**我們自己的** dashboard/分析 DB(由 Redis Streams 餵)。
- **ZeroMQ:非原生**。要的話建成 Redis Streams 下游 relay。第一版很可能不需要。
- **部署**:自行容器化 TradingNode(uv + Python 3.12–3.14),compose 旁掛 Redis(+ Postgres + FastAPI/WebSocket relay)。唯一上游背書的 Docker 件是 IB Gateway 容器。
- **Adapters**:加密覆蓋強(data+exec);IB 是通往傳統資產的橋;Databento/Tardis 僅資料。
- 最低信心、需依版本再確認:**PostgreSQL cache backend 的 Python API 成熟度**。
