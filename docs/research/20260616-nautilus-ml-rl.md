# 研究:NautilusTrader 的 ML / DL / RL 整合

> 來源:官方文件 + GitHub repo/issues + 社群來源。整理於 2026-06-16。
> 對 JimQ「整合強化學習」這個核心目標,本文是**最關鍵**的研究,結論誠實標註不確定性。

## 摘要(先看結論)

- **自訂/另類資料:一級支援、文件完整。** 繼承 `Data` 或用 `@customdataclass`,經 message bus `subscribe_data`/`publish_data`,並可寫入 `ParquetDataCatalog`。這是最乾淨的整合路徑(衛星、情緒、自訂特徵皆走這條)。
- **策略內 ML 推論:設計上支援,但全 DIY。** 在 `on_start` 載入 PyTorch/TF 模型,在 `on_bar`/`on_quote_tick` 呼叫。Nautilus 無任何 ML 抽象,就是 callback 裡的純 Python。延遲是真正的顧慮。
- **RL:沒有原生 gym/Gymnasium wrapper,沒有官方 RL 範例。** ⚠️ 這是最重要的發現。行銷文案說「能訓練 RL agent、不需 environment wrapper」是**宣傳,不是功能**。backtest 引擎是**跑到底(run-to-completion)的事件迴圈** `engine.run()`,與 RL 的 `step()`/`reset()` 範式**阻抗不匹配**。
- **訓練 vs 推論邊界:** 標準做法 catalog → DataFrame → 離線 GPU 訓練 → 輸出權重 → 策略內載入推論。雙向都支援良好。

## 1. 自訂 / 另類資料(支援良好)

- 所有自訂資料繼承 `nautilus_trader.core.Data`,需 `ts_event`/`ts_init` 兩個奈秒戳。
- 兩種定義法:手動 subclass(實作序列化),或 **`@customdataclass` 裝飾器**(自動生成 dict/bytes/Arrow 序列化,推薦)。
```python
from nautilus_trader.core import Data
from nautilus_trader.model.custom import customdataclass

@customdataclass
class SatelliteSignal(Data):
    region: str = ""
    activity_index: float = 0.0
```
- 經 message bus 餵入:`publish_data(DataType(SatelliteSignal, metadata={...}), signal)` / `subscribe_data(...)` → `on_data`。`metadata` 進入 topic,可細緻路由。
- Catalog 支援:`register_serializable_type` + `register_arrow` 後 `catalog.write_data([...])`。Backtest 用 `BacktestDataConfig(data_cls=SatelliteSignal, ...)`。自訂資料會與市場資料按時間正確交錯進同一事件流。
- **結論**:任意外部資料(衛星、情緒、特徵)是已解決問題。寫 Adapter/Actor 即時 `publish_data`,或預載 catalog 做確定性 backtest。

## 2. 策略內 ML 推論

- Nautilus **無 ML 專屬 API**,就是快速的 Python 事件迴圈,把模型塞進 callback。
```python
class MLStrategy(Strategy):
    def on_start(self):
        import torch
        self.model = torch.jit.load("model.pt"); self.model.eval()
        self.register_indicator_for_bars(self.bar_type, self.ema)
        self.request_bars(self.bar_type); self.subscribe_bars(self.bar_type)
    def on_bar(self, bar):
        features = self._build_features(bar)
        with torch.no_grad():
            signal = self.model(features)
        if signal > threshold: self.submit_order(...)
```
- 特徵工程位置(優先序):**註冊 Indicator**(增量、不重算)> **專屬 Actor**(`publish_data` 特徵物件,多策略共用)> callback 內聯。
- ⚠️ **延遲(真實顧慮)**:runtime 在事件迴圈內是**同步**的,慢的 `model()` 會阻塞事件處理。
  - backtest 只影響 wall-clock 速度。
  - **live 很重要**:推論要小、用 `torch.jit`/ONNX Runtime、增量算特徵。重模型應**跑在獨立行程**(推論服務),接受額外延遲,別阻塞引擎執行緒。

## 3. 強化學習 — 最關鍵的問題

### 發現:沒有原生 Gym/Gymnasium 支援,沒有官方 RL 範例

深度搜尋(docs/repo/examples/issues/`nautilus_experiments`)後確認:**無原生 `step()`/`reset()` 環境、無 wrapper、無官方 RL 範例**。所有「快到能訓練 RL agent」的說法都來自行銷/部落格文案,不對應任何已出貨的功能。視為願景。

### 阻抗不匹配(核心架構問題)

- **RL(Gymnasium)是 pull-based / 控制反轉在 agent 端**:訓練迴圈擁有時鐘 — `reset()` 後反覆 `obs, reward, done, info = env.step(action)`。環境必須**暫停、交出控制權、收到 action、再前進**。
- **Nautilus backtest 引擎是 push-based / 跑到底**:`engine.run()` 呼叫**一次**就內部把整個事件迴圈跑完,把事件推進策略 callback。**沒有公開的 `engine.step()`** 可前進一個事件就交還控制。
- 所以 **Nautilus 事件迴圈與 `step()` 範式原生不相容**。這直接回答 build-vs-buy。

### 若要在 Nautilus 上建 RL,可行架構(由便利→高擬真)

- **Option A — Callback 即 agent(策略內推論、訓練在外)**:離線在標準環境訓練 RL policy,把**訓練好的 policy** 當成 Nautilus `Strategy` 推論跑。完美可行、風險最低,但 Nautilus 只是**評估/部署**載具,非訓練環境。
- **Option B — 用 thread/coroutine 反轉控制(讓 `run()` 看起來像 `step()`)**:背景執行緒跑 `engine.run()`,在 callback 內放**阻塞交接**(兩個 `queue.Queue`):每個決策事件 callback 推 observation 並**阻塞**等 action;agent 端 `env.step(action)` 推 action 並阻塞等下個 observation。最忠實地「拿 Nautilus 當模擬器」,免費得到擬真成交/PnL/手續費/滑點。代價:執行緒同步複雜、每步 context-switch 開銷(侵蝕 Nautilus 速度優勢)、`reset()` 語意棘手、難向量化平行環境(要 N 行程跑 N 引擎)。可建但是**無上游背書的客製工程**。
- **Option C — Chunked/streaming run + 外層迴圈**:每個 chunk 仍內部跑到底,只給**粗粒度**(per-chunk)控制,**非** per-event `step()`。只適合很粗的 episode 邊界。
- **Option D — 訓練不用 Nautilus 迴圈,另用 Gym 環境**:訓練用專用交易 Gym(Gym-Trading-Env / gym-anytrading / FinRL),**驗證/部署**在 Nautilus 拿擬真執行。完全迴避阻抗不匹配。風險:**訓練/評估模擬器分歧**(Gym fill model ≠ Nautilus),需謹慎驗證,理想上用有限 Option-B 微調收斂。

### 對 JimQ 決策的建議

- 若需**高吞吐、向量化 RL 訓練**,Nautilus 跑到底的迴圈會與你作對。建忠實 `step()`(Option B)可行但是無上游支援的自建基礎設施,每步交接開銷侵蝕速度。
- 多數團隊落腳的務實切分:**用輕量/標準 Gym 環境訓練(D),再用 Nautilus 當高擬真 backtest + live 執行層部署 policy(A)**,必要時用有限 Option-B 微調補模擬落差。讓 Nautilus 做它真正最強的(擬真確定性執行 + research→live parity),不硬把 `step()` 套到不為此而生的引擎上。
- **切勿假設有任何原生 RL 功能 — 截至此研究沒有。**

## 4. 訓練 vs 推論分離

- **資料出口 = catalog**:所有資料以 Nautilus Parquet(Arrow)儲存。⚠️ catalog 已移除 DataFrame helper(維護兩條路徑太難,issue #991),回傳 Nautilus 物件。要訓練張量:(a) 直接讀底層 Parquet 進 pandas/Polars/PyArrow,或 (b) 查物件後 `to_dict()` → DataFrame。
- **權重入口**:輸出 TorchScript/ONNX/權重,`on_start` 載入一次,callback 推論。
- 乾淨分離:離線(GPU)讀 catalog Parquet → 張量 → 訓練 DL/RL → 輸出權重;線上(引擎)載權重 → 逐事件推論。為避免 train/serve skew,特徵碼要 backtest 與 live 共用。

## 5. 指標與特徵管線

- 內建指標庫(Rust 實作,`nautilus_indicators` crate)。
- 註冊自動更新:`register_indicator_for_bars(bar_type, indicator)` 等,資料到自動餵,callback 內讀 `indicator.value`。
- 自訂指標:subclass `nautilus_trader.indicators.base.Indicator`,實作 `handle_bar`/`update_raw`/`_reset`。
- 作為特徵層:註冊指標是 ML 的慣用高效特徵層(增量、可共用)。複合特徵在 Actor 算後 `publish_data`。

## 信心 / 不確定性註記

- **高信心**:自訂資料、catalog、指標、ML 推論模式、`engine.run()` 跑到底的本質 — 皆來自官方 docs/原始碼。
- **高信心(否定)**:無原生 Gym wrapper、無官方 RL 範例。docs/repo/examples/issues 都找不到,RL 說法皆出自宣傳文。
- **中信心**:Option-B thread-handoff 橋接的細節與 `engine.reset()` 的 per-episode 行為 — 由 API 推論,無已知範例。**承諾架構前先做小原型驗證。**
