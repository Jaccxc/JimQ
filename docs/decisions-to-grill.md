# JimQ 待決策清單(給 /grill-me)

> 日期:2026-06-16 · 用途:你 AFK 回來後執行 `/grill-me`,逐題拍板。
> 每題附我的**建議預設**(可直接接受)與**為何重要**。標 ⭐ 者最影響架構。
> 建議順序:先決「戰略層」(決定一切),再「架構層」,再「實作細節」。

---

## A. 戰略層(決定其餘所有決策)

### ⭐ A1. 第一個交易市場與資產
- **問**:第一期交易什麼?加密(現貨/永續)、美股、期貨、FX?
- **建議**:加密 + Binance/Bybit,先 testnet。adapter data+exec 齊全、24/7、API 易、歷史資料免費,最快打通。
- **為何重要**:決定 adapter、資料來源、延遲預算、法規/稅務。

### ⭐ A2. 交易頻率 / 持倉時間尺度
- **問**:目標持倉多久?秒級(HFT)/ 分鐘 / 小時(intraday)/ 天~週(swing)?
- **建議**:intraday~swing(分鐘到小時)。非 HFT — Python + 策略內推論不適合超低延遲,ML/RL 訊號天然中低頻。
- **為何重要**:決定資料粒度(tick vs bar)、整套延遲預算、是否需要 order book L2/L3。

### ⭐ A3. 第一優先:穩定獲利 vs RL 研究
- **問**:先做一條「簡單但可驗證獲利」的策略打通全鏈並上線,還是優先投入 RL/DL 研究?
- **建議**:先 tracer bullet(簡單策略)打通 backtest→sandbox→live + dashboard,**再**疊 RL。賺錢要先有能穩定運轉、可信任的管線。
- **為何重要**:決定路線圖順序與資源投放。

### A4. 資金、風險、真錢時程
- **問**:初始資金規模?可承受最大回撤?多久內想上真錢?
- **建議**:一律先 paper/testnet,通過 sandbox + 風控(名目上限/rate limit/kill switch)再小額真錢。
- **為何重要**:決定風控參數、live 上線關卡的嚴格度。

---

## B. 架構層(大叉路)

### ⭐ B1. RL 整合路線(最重大技術決策)
- **背景**:Nautilus **無原生 gym wrapper**,`engine.run()`(跑到底)與 RL `step()` 阻抗不匹配。
- **問**:接受「獨立 Gym 環境訓練 + Nautilus 部署/評估」(Option D+A),還是要在 Nautilus 上自建 `step()` 訓練橋接(Option B)?
- **建議**:D+A 務實路線;Option-B 只當後期微調原型(風險高、無上游支援)。
- **為何重要**:這決定 research 層的整個設計。

### ⭐ B2. ZeroMQ 去留
- **背景**:你提到想用 ZeroMQ,但 Nautilus 非原生用它;Redis Streams 已能做 engine→dashboard + 命令,且 Nautilus 原生支援。
- **問**:第一期能否砍掉 ZeroMQ 只用 Redis Streams?還是你有特定用途(未來多機/多策略分散、超低延遲扇出)非它不可?
- **建議**:第一期不引入;日後需要再加「訂 Redis Streams → ZeroMQ 轉發」的 relay。
- **為何重要**:少一個元件、少一層複雜度。

### B3. Postgres 角色
- **問**:Postgres 只放我們的應用資料(交易日誌/backtest 結果/策略參數/模型 metadata),不當 Nautilus cache(未成熟)— 同意?
- **建議**:同意。Nautilus 狀態用 Redis。
- **附問**:dashboard 的歷史 bar 查詢用 Postgres/TimescaleDB,還是直接查 Parquet/DuckDB?(建議先 DuckDB/Parquet)

### B4. 引擎↔外圍通訊細節
- **問**:命令路徑(start/stop/調參)用「第二條 Redis stream 由節點 Actor 消費」,還是「API 直接控制引擎行程」?
- **建議**:Redis command stream(解耦、可重播、可審計)。

---

## C. 技術棧細節

### C1. Repo 形態
- **問**:Monorepo + uv workspace 可以嗎?`web` 放 monorepo 內(用 OpenAPI 生成 TS 型別對齊)?
- **建議**:是。

### C2. research 環境隔離
- **問**:`research`(CUDA torch 重依賴)是否拆出 uv workspace 用獨立 venv,避免拖累 engine/api?
- **建議**:拆出獨立環境。

### C3. Nautilus 版本
- **問**:Pin 一個 stable PyPI release(免編 Rust)?有需要 develop 才有的功能嗎?
- **建議**:pin stable。

### C4. Python 版本
- **問**:Python 3.12(Nautilus 支援 3.12–3.14)?需確認 torch 等 DL/RL 套件相容。
- **建議**:3.12。

### C5. 圖表庫與標註
- **問**:用 Lightweight Charts v5(須顯示 TradingView 標註)可接受嗎?反感標註則用 klinecharts(免標註)。
- **建議**:Lightweight Charts;標註是小連結,容易接受。

### C6. 歷史資料來源
- **問**:第一期用交易所免費歷史(Binance klines)?需要 tick / order book L2/L3 還是 bar 就夠?資料預算?
- **建議**:先免費 bar 級;需要更細再評估 Databento/Tardis(付費)。

### C7. DL/RL 框架與實驗追蹤
- **問**:PyTorch ✓;RL 框架(Stable-Baselines3 起步 / Ray RLlib 擴展 / 自寫)?實驗追蹤用 MLflow(自架)還是 W&B(雲端付費)?GPU 規格(單卡/多卡)?
- **建議**:PyTorch + SB3 起步 + MLflow 自架。

### C8. 「crazy 模型」具體願景
- **問**:你說的「GPU 上的 crazy 模型」具體想像是什麼?(order book 上的 transformer?圖表 CNN?LSTM 序列?多模型 ensemble?)RL 的 observation/action/reward 初步構想?
- **為何重要**:影響 research 層模型抽象與資料管線設計;也幫我判斷 GPU/資料規模。

### C9. 另類資料(衛星等)
- **問**:衛星/另類資料是「監督式訊號特徵」(餵 DL 模型),還是要進 RL observation?何時排入(建議 Phase 6,最後)?
- **建議**:當自訂資料 Actor → 特徵,排在管線打通之後。

### C10. 大型資料/權重版本管理
- **問**:catalog 資料與模型權重用 git-lfs / DVC / 純本地 + 物件儲存(MinIO/S3)?
- **建議**:本地 + 之後 MinIO;權重用簡單 model store + Postgres metadata。

---

## D. 我需要你回答才能繼續的最少集合(若只想快答)
1. **A1 市場** + **A2 頻率**(決定一切)
2. **A3 優先序**(簡單策略先 vs RL 先)
3. **B1 RL 路線**(接受 D+A 嗎)
4. **B2 ZeroMQ**(能否第一期砍)
5. **C8 模型願景**(讓我理解你的「crazy 模型」)

其餘可先接受我的建議預設,日後再調。
