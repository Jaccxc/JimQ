# JimQ 技術棧決策(ADR 草案)

> 日期:2026-06-16 · 狀態:**草案,多數待 `/grill-me` 拍板**
> 格式:每條決策含「立場 / 理由 / 替代方案 / 待確認」。立場是我的建議預設,非定案。

---

## AD-1 ⭐ RL 整合策略(最重大)

- **立場**:**Option D + A** — 在獨立 Gym/Gymnasium 環境訓練 RL policy,用 Nautilus 當高擬真 backtest 與 live 部署層;後期視需要用 Option-B(thread-handoff 讓 `engine.run()` 像 `step()`)對 Nautilus 微調收斂模擬落差。
- **理由**:Nautilus **無原生 gym wrapper**,`engine.run()` 跑到底與 RL `step()` 阻抗不匹配。硬建 `step()` 橋接可行但無上游支援、每步交接開銷侵蝕速度。先讓 Nautilus 做它最強的。
- **替代**:Option B 全程(高擬真但高風險客製);純 FinRL 類框架(離 Nautilus 太遠,parity 喪失)。
- **待確認**:RL 框架(SB3 / Ray RLlib / CleanRL / 自寫)?向量化平行訓練需求?第一個 RL 問題的 observation/action/reward 設計?

## AD-2 ZeroMQ 是否引入

- **立場**:**第一期不引入。** Redis Streams 已能做 engine→dashboard 與命令路徑,且 Nautilus 原生支援。
- **理由**:ZeroMQ 非 Nautilus 原生,引入需自建 relay 且失去持久化/重播。速度不是第一期瓶頸。
- **替代**:日後若需超低延遲扇出或多服務解耦,加一個訂 Redis Streams 的 ZeroMQ relay。
- **待確認**:你明確提到想用 ZeroMQ — 是有特定用途(例如未來多策略/多機分散),還是可接受先用 Redis Streams?

## AD-3 PostgreSQL 角色

- **立場**:Postgres **僅放我們自己的應用資料**(交易日誌、backtest 結果、策略/參數版本、模型登記 metadata、dashboard 查詢)。**不**當 Nautilus cache backend。
- **理由**:Nautilus 的 Postgres cache backend 在 Rust 層存在但 Python API 未成熟、文件不全;Redis 才是成熟路徑。
- **替代**:等 Nautilus Postgres backend 成熟後評估遷移。
- **待確認**:歷史 bar 給 dashboard 查詢要用 Postgres/TimescaleDB,還是直接查 Parquet/DuckDB?

## AD-4 第一個交易市場 / 資產類別

- **立場**:**加密貨幣(Binance 或 Bybit)**,先 testnet/paper。
- **理由**:adapter 提供完整 data+exec、24/7、API 門檻低、歷史資料免費易取、最快打通 tracer bullet。傳統資產要 IB(TWS/Gateway 較重)。
- **替代**:傳統資產走 Interactive Brokers;資料品質走 Databento(付費,僅資料)。
- **待確認**:你想交易什麼?加密 / 美股 / 期貨 / FX?現貨還是合約/永續?

## AD-5 引擎 ↔ 外圍通訊

- **立場**:**Redis Streams**(資料出 + 命令入)。
- **理由**:Nautilus 原生發佈 Redis Streams,持久化/重播/consumer group,單一依賴,本地到多 worker 不變。
- **待確認**:命令路徑用第二條 stream 由節點 Actor 消費,還是 API 直接呼叫引擎行程?

## AD-6 前端圖表庫

- **立場**:**TradingView Lightweight Charts v5**(備案 klinecharts)。
- **理由**:專為金融、體積小、priceLine + seriesMarkers + primitives 完美對應進場/SL/TP/箭頭。
- **注意**:Apache-2.0 但**須顯示標註**。若反感標註則用 klinecharts(免標註)。
- **待確認**:可接受 TradingView 標註嗎?

## AD-7 Repo 形態與套件管理

- **立場**:**Monorepo + uv workspace**。Python 套件(`engine`/`research`/`api`/共用 `libs`)用 uv workspace 管理;`web` 獨立 npm 專案於同 repo。
- **理由**:共用型別/schema、原子提交、單一 CI;你已把整個資料夾推上 GitHub。
- **待確認**:Python 各套件共用單一 venv(uv workspace)還是各自獨立?`research` 因 CUDA 依賴重,是否獨立環境?

## AD-8 Nautilus 版本策略

- **立場**:**Pin 一個 stable release**(PyPI wheel,免編 Rust)。
- **理由**:`develop`/nightly 有破壞性變更;穩定基底利於打地基。
- **待確認**:需要 develop 才有的功能嗎?(目前看不需要)

## AD-9 Python 版本

- **立場**:**Python 3.12**(Nautilus 支援 3.12–3.14,3.12 生態最穩;Linux 高精度 wheel)。
- **待確認**:DL/RL 套件(torch 等)在 3.12 相容性確認。

## AD-10 歷史資料來源

- **立場**:第一期用**交易所免費歷史資料**(Binance klines/aggTrades)灌 catalog。
- **替代**:Databento(付費,跨市場高品質)、Tardis(crypto)。
- **待確認**:資料預算?需要 tick/order book L2/L3 還是 bar 就夠?

## AD-11 DL/RL 框架與實驗追蹤

- **立場**:PyTorch;RL 框架待定(傾向 Stable-Baselines3 起步,Ray RLlib 做向量化擴展);實驗追蹤用 **MLflow**(可自架,docker)。
- **待確認**:有偏好框架嗎?要不要 Weights & Biases(雲端,付費)?GPU 規格(單卡/多卡)?

## AD-12 真錢 vs 紙上 / 風控

- **立場**:**一律先 testnet/paper**,通過 sandbox 關卡 + 風控限制(名目上限、rate limit、kill switch)後才考慮小額真錢。
- **待確認**:初始資金規模?可承受回撤?live 真錢的時程期望?

## AD-13 交易頻率 / 延遲需求

- **立場**:**先做 intraday/swing(分鐘~小時級)**,非 HFT。
- **理由**:HFT 對基礎設施延遲要求極高,Python+策略內推論不適合;ML/RL 訊號天然偏中低頻。
- **待確認**:你心中的持倉時間尺度?(秒/分/時/日)這決定資料粒度與整套延遲預算。

---

## 待 grill 的「大叉路」(最影響架構)

1. **AD-1 RL 路線**:接受 D+A 務實路線,還是要堅持在 Nautilus 上建原生 `step()` 訓練?
2. **AD-2 ZeroMQ**:可否第一期砍掉,只用 Redis Streams?
3. **AD-4 / AD-13 市場與頻率**:交易什麼、持倉多久 — 這決定資料、adapter、延遲預算。
4. **優先序**:先求「簡單但穩定獲利」的策略打通全鏈,還是優先投入 RL 研究?
5. **AD-12 風險**:資金規模、真錢時程、可承受回撤。
