# JimQ — 策略生命週期手冊(開發 → 測試 → 上線賺錢)

> 一支策略從「想法」到「在市場上跑真錢」要經過哪些關卡,以及每關用什麼指令。
> 核心原則:**研究→回測→live 用同一份策略碼**(Nautilus parity),只換 adapter/設定。
> ⛔ **真錢上線是人類專屬硬閘**(平台預設鎖死 testnet);自動化只到 testnet paper 為止。

```
[0 選型] → [1 開發] → [2 回測評估] → [3 研究驗證] → [4 testnet paper] → ⛔[5 真錢上線]
                ↑__________________迭代__________________↓        人類授權才跨
```

---

## 階段 0 — 選策略型態

| 型態 | 適合 | 怎麼做 | 範本 |
|---|---|---|---|
| **規則型**(rule-based) | EMA 交叉、突破、均值回歸等明確規則 | 寫一個 Nautilus `Strategy` 子類,`on_bar` 裡判斷 → bracket 下單 | `engine/jimq_engine/strategies/ema_cross.py` |
| **模型型**(model-based) | DL/RL/序列/多模態,靠資料學訊號 | 走研究管線(dataset→train→register),用通用 `ModelInferenceStrategy` 載模型推論 | `engine/jimq_engine/strategies/model_inference.py` + `research/` |

兩條路最後都產出「一個 Nautilus Strategy」,後面 2~5 階段共用。

---

## 階段 1 — 開發

### 規則型
1. 複製 `ema_cross.py` 當骨架,新增 `engine/jimq_engine/strategies/<your>.py`。
2. 在 `on_bar`(**收線才觸發**,保 parity)寫進出場邏輯,用 bracket(MARKET 進場 + STOP_MARKET SL + LIMIT TP);Binance 期貨不支援 OCO 條件單,純 MARKET 進場見 `use_bracket=False` 路徑。
3. 參數(週期/單量)做成 strategy config 欄位,方便回測掃參。

### 模型型(研究管線)
完整跑法見 **[`20260616-research-demo.md`](./20260616-research-demo.md)**。一句話:
```bash
cd research && uv sync
uv run python -m jimq_research.training.run_research_demo   # dataset→train→register→model-backtest→MLflow
```
真正做 alpha 只改 **5 個替換點**(其餘 plumbing 不動,因為模型類型無關 C8):

| # | 替換點 | 檔案 |
|---|---|---|
| 1 特徵 | `run_research_demo.build_demo_dataset` | 走 `jimq_core.features`(與策略共用,反 train/serve skew) |
| 2 標籤/獎勵 | `run_research_demo._next_up_label` | 你的標籤或 RL reward |
| 3 模型 | `jimq_research.export.baseline.train_baseline_stub` | 真模型,需有 `predict(features)->signal` |
| 4 推論特徵 | `ModelInferenceStrategy._build_features` | 與 #1 **同一組特徵** |
| 5 訊號語意 | `ModelInferenceStrategy._signal_to_action` | 機率閾值/回歸值/RL 動作 |

> 程式內每處都有 `USER REPLACEMENT POINT` 註解。這 5 點是**你的領域**(模型/特徵/資料),平台不替你決定。

---

## 階段 2 — 回測評估

```bash
make up && make exp          # 最快:灌真歷史 + 跑回測 → 開 127.0.0.1:8080 Backtest 頁看
```
或從 **Backtest 分頁的表單**選 symbol/tf/strategy/參數/日期 → Run,圖即時長出、History 可比較過往 run。
腳本路徑:`scripts/run_ema_backtest.py`、`scripts/run_streaming_backtest.py`。

**看什麼**:total_return、num_fills(>0 代表下單鏈通)、num_trades、權益曲線。
**迭代**:改參數/邏輯 → 重跑 → 比較。⚠️ 小心過度擬合(見階段 3 缺口)。

---

## 階段 3 — 研究驗證(模型型)

研究迴圈把結果記進 **MLflow** + **model_registry**(Postgres):
```bash
cd research
uv run python -m jimq_research.training.run_research_demo
uv run python -m pytest tests/ -q          # 行為驗收
```
- MLflow:`http://localhost:5000`(或本地 sqlite 退路),比較不同模型版本的 num_fills/total_return。
- model_registry:`curl -s http://127.0.0.1:8000/api/v1/models` 或 Research 分頁看已登錄模型、觸發 build dataset / train job、Deploy 模型→backtest。

> ⚠️ stub 模型報酬為負是**預期**的——它只證明 plumbing,不是 alpha。真 alpha 是你替換 5 點後的事。

---

## 階段 4 — testnet paper(live 行為驗證,假錢)

**這是上真錢前的最後一關**,用 Binance USDT-M Futures **testnet** 跑真連線、下假錢單:
```bash
make up
make paper          # = scripts/run_live_trade.py;ema_cross 在真即時 1m bar 下 0.001 BTC paper 單
#   --max-notional 200  --max-order-submit-rate 10/00:00:01   # 風控旗標
```
開 **Live 分頁**看真 live 訂單/成交/部位/PnL。風控/kill/對帳細節見 [`20260616-live-data-testnet.md`](./20260616-live-data-testnet.md) 第 7 節:
- `max_notional_per_order` + order rate throttler(⚠️ 名目上限在期貨 MARGIN 帳戶目前不觸發,見缺口)、`bypass=False`。
- Kill switch:撤未成交 → 平倉 → 停;reconciliation 重啟對帳。

**parity 保證**:這裡跑的策略碼和階段 2 回測**完全相同**,只換 data/exec adapter(Nautilus 核心保證)。paper 表現 ≈ 真 live 行為(扣掉滑價/延遲差異)。

> 建議:讓 paper 跑一段時間(數小時~數天),觀察真實成交、滑價、部位管理是否如預期,再考慮真錢。

---

## ⛔ 階段 5 — 真錢上線(人類專屬硬閘,平台不自動跨)

**目前平台預設鎖死 testnet**:`engine/jimq_engine/nodes/live.py` 的 `assert_testnet_only()` 對任何非 testnet 設定拋 `MainnetBlockedError`(三重 assert)。這是**刻意的安全設計**。

要真上線(**需你明示授權 + 親自操作**),缺的東西見下方缺口清單。原則:
1. 真錢永遠不自動化決定;capital 配置、部位大小、真風控上限是你拍板。
2. 先小資金、嚴風控、有監控告警,再逐步放大。
3. 每次 ramp 都人工確認。

---

## 🚧 讓「上線賺錢」更順的已知缺口(誠實清單)

這些是目前平台**還沒做滿**、要真正賺錢前該補的(都屬可規劃的平台卡,真錢決策仍是你的):

| 缺口 | 現況 | 要補什麼 |
|---|---|---|
| **策略選擇接線到 live 節點** | `run_live_trade.py` 寫死 ema_cross | 讓任意「已登錄的策略/模型」一鍵推到 live 節點(strategy/model selector → live node) |
| **真錢 adapter 路徑** | 鎖死 testnet(assert_testnet_only) | 受控解鎖 mainnet(真金鑰、環境旗標、雙人確認式 gate) |
| **名目風控對期貨生效** | Nautilus 1.228 對 MARGIN 帳戶 early-return,期貨名目上限不觸發 | 自建名目前置檢查或等上游修;目前靠 rate throttler + kill + 小單量 |
| **樣本外/walk-forward 驗證** | 只有單段 backtest | 加 walk-forward、OOS、參數穩健度框架,防過度擬合 |
| **paper/live 績效日誌累積** | 事件即時顯示,未長期累積分析 | 把成交/部位/PnL 落 Postgres 做長期績效追蹤、回撤統計 |
| **監控告警** | 無 | live 跑真錢需 PnL/部位/斷線告警、自動 kill 條件 |

---

## 一頁速查

| 階段 | 指令 | 看哪 |
|---|---|---|
| 開發 | 編輯 `strategies/` 或 `research/` 5 替換點 | 程式 |
| 回測 | `make exp` / Backtest 表單 | Backtest 頁 |
| 研究 | `cd research && uv run python -m jimq_research.training.run_research_demo` | MLflow / Research 頁 |
| paper | `make paper` | Live 頁 |
| 真錢 | ⛔ 人類授權,缺口待補 | — |

相關:[`20260616-research-demo.md`](./20260616-research-demo.md)、[`20260616-live-data-testnet.md`](./20260616-live-data-testnet.md)、[`20260616-quickstart.md`](./20260616-quickstart.md)、`DEV_CONTRACT_AFK.md`。
