# JimQ — 端到端研究 demo Runbook(卡 #18 / P3-S5)

從零到看到**完整研究迴圈**結果:
catalog → dataset builder → 訓練佔位 stub baseline → 登錄 model_registry →
**模型驅動的 backtest**(通用 `ModelInferenceStrategy`,反 train/serve skew)→
結果記入 MLflow。

> 真相來源:`docs/design/20260616-1845-repo-structure-final.md`、
> `docs/design/20260616-1830-decisions-confirmed.md`(C8 模型類型無關可插拔)、
> `DEV_CONTRACT_AFK.md`。全程跑在**本機**(localhost-only;鐵律 4/5),不連任何遠端。
>
> ⚠️ **stub 模型只證明 PLUMBING 通,不是 alpha**。它是你要替換的骨架。
> 替換點集中列在最後一節。

---

## 0. 前置需求

| 項目 | 說明 |
|---|---|
| Python 3.12 + uv | `research/` 是**獨立 venv**(CUDA/torch 重依賴,不在 root workspace) |
| Docker(redis+postgres) | localhost,長駐運行(`docker compose up -d redis postgres`) |
| catalog 有資料 | `data/catalog` 需有 BTCUSDT-PERP 1m bars(見步驟 2;若已 ingest 可略) |
| model_registry 表 | 由 api 的手寫 alembic 建(`alembic upgrade head`,卡 #17 已就緒) |
| MLflow(選用) | 不啟 docker 服務時自動退回本地 sqlite `data/mlflow/mlflow.db` |

確認基礎服務:

```bash
cd /home/jacc/projects/JimQ
docker ps --format '{{.Names}}\t{{.Status}}'   # 應見 jimq-postgres / jimq-redis healthy
```

---

## 1. 安裝 research venv(首次)

```bash
cd /home/jacc/projects/JimQ/research
uv sync                # 建 .venv,裝 torch(cpu)/sklearn/polars/mlflow/nautilus + jimq_core/jimq_engine
```

> `jimq_core` / `jimq_engine` 以 editable path 依賴帶入 —— dataset builder 與
> `ModelInferenceStrategy` 因此**共用同一份** `jimq_core.features`(EMA),消除
> train/serve skew。

---

## 2. 確保 catalog 有 bars(若已有可略)

demo 從共享 `ParquetDataCatalog`(預設 `data/catalog`,或 `JIMQ_CATALOG_PATH`)讀
bars。若尚無資料,用 Phase 1 的 ingest(engine):

```bash
cd /home/jacc/projects/JimQ
# 真 BTCUSDT-PERP 1m 歷史灌入 catalog(engine 一次性 job;見 docs/RUNBOOK.md 步驟 2)
docker compose --profile demo run --rm engine
```

確認 bars 數:

```bash
cd /home/jacc/projects/JimQ/research
uv run python -c "from jimq_engine.catalog.ingest import open_catalog, BAR_TYPE_1M, query_bars; print('1m bars:', len(query_bars(open_catalog(), BAR_TYPE_1M)))"
# 1m bars: 1475   (示意)
```

---

## 3.(選用)啟 MLflow docker 服務

```bash
cd /home/jacc/projects/JimQ
docker compose --profile research up -d mlflow          # localhost:5000
export MLFLOW_TRACKING_URI=http://localhost:5000
```

不做這步也可以 —— tracking wrapper 會自動退回本地 sqlite `data/mlflow/mlflow.db`,
demo 照常記得到 run(離線可看)。

---

## 4. 跑端到端研究 demo

```bash
cd /home/jacc/projects/JimQ/research
uv run python -m jimq_research.training.run_research_demo
```

腳本依序串起(全部復用既有元件,不重造輪子):

1. **dataset**(`jimq_research.data.build_dataset`,#14):catalog → 兩條 EMA 特徵
   (`ema_fast`/`ema_slow`,復用 `jimq_core.features`)+ 下一根方向標籤 `label_up`。
2. **train stub**(`jimq_research.export.train_baseline_stub`,#18):LogisticRegression
   佔位 baseline → 包成 `predict(features_dict)->signal` 的 `PredictModel`。
3. **register**(#17):artifact joblib 序列化到 `data/models/<name>/<version>/`
   (對齊 api `ModelStore` 磁碟慣例)+ metadata INSERT 進 Postgres `model_registry`。
4. **model 驅動 backtest**(#4 引擎 + #18 策略):從 artifact 載回模型 → 通用
   `ModelInferenceStrategy` 在 `on_bar` 用**同一份** `jimq_core.features` 算特徵 →
   `model.predict` 輸出訊號 → bracket 下單(MARKET 進場 + STOP_MARKET SL + LIMIT TP)。
5. **MLflow**(#16):dataset 列數 / 下單數 / 成交數 / 報酬 / 餘額記成一個 run。

預期輸出(數值依資料而異):

```
=== RESEARCH DEMO RESULT ===
    dataset_rows: 1475
      model_name: baseline-stub
   model_version: v-xxxxxxxx
    artifact_dir: /home/jacc/projects/JimQ/data/models/baseline-stub/v-xxxxxxxx
     registry_id: 8
      num_orders: 5823          ← 模型推論驅動下單
       num_fills: 2911          ← bracket 進場成交(plumbing 通)
      num_trades: 0
    total_return: -0.0046...
   final_balance: 995325.45...
   mlflow_run_id: 35456499...
```

> `num_fills > 0` 證明「模型輸出 → 對應下單 → 成交」這條鏈通了。報酬為負是預期的
> —— **stub 沒有 alpha**。

常用旗標:

```bash
# 不登錄 Postgres / 不記 MLflow(純跑 plumbing):
uv run python -m jimq_research.training.run_research_demo --no-register --no-mlflow

# 指定 MLflow experiment 名:
uv run python -m jimq_research.training.run_research_demo --mlflow-experiment my-exp
```

---

## 5. 驗證結果落地

**model_registry(Postgres,app 級查詢):**

```bash
cd /home/jacc/projects/JimQ/research
uv run python -c "
from sqlalchemy import create_engine, text
from jimq_research.training.store import local_engine_url
e=create_engine(local_engine_url())
with e.connect() as c:
    for r in c.execute(text('select id,name,version,framework,artifact_path from model_registry order by id desc limit 5')).mappings():
        print(dict(r))
"
```

或經 api 端點(若 api 在跑):`curl -s http://127.0.0.1:8000/api/v1/models`(#17)。

**MLflow run:**

- docker 服務:瀏覽器開 `http://localhost:5000`,選 experiment `research-demo`。
- 本地 sqlite 退路:

```bash
cd /home/jacc/projects/JimQ/research
# 退路 sqlite db 路徑相對 CWD:從 research/ 跑時即 research/data/mlflow/mlflow.db。
uv run python -c "
import mlflow
mlflow.set_tracking_uri('sqlite:///data/mlflow/mlflow.db')
exp=mlflow.get_experiment_by_name('research-demo')
print(mlflow.search_runs([exp.experiment_id])[['run_id','metrics.num_fills','metrics.total_return']].head())
"
```

---

## 6. 跑測試(行為驗收)

```bash
# 策略行為(模型輸出驅動下單 — 假 predict 注入製造訊號):
cd /home/jacc/projects/JimQ
.venv/bin/python -m pytest engine/tests/test_model_inference_strategy.py -q

# 端到端 demo(dataset→train→artifact→model backtest 成交→MLflow run)+ registry round-trip:
cd /home/jacc/projects/JimQ/research
uv run python -m pytest tests/test_research_demo_e2e.py tests/test_baseline_stub.py tests/test_model_registry_glue.py -q
```

---

## 7. ⭐ 使用者替換點(把骨架換成真研究)

stub demo 的唯一目的是**證明 plumbing**。要做真 alpha 時,只改下列「介面點」,
plumbing(registry / 引擎 / 串流)完全不動 —— 因為一切都是**模型類型無關**的(C8):

| # | 替換點 | 檔案 / 函式 | 換成什麼 |
|---|---|---|---|
| 1 | **特徵** | `jimq_research.training.run_research_demo.build_demo_dataset` | 你的真特徵組合。務必繼續走 `jimq_core.features`(dataset builder 與策略**共用同一份**),否則 train/serve skew |
| 2 | **標籤 / 獎勵** | `run_research_demo._next_up_label`(或 RL 用獎勵) | 你的真標籤(多分類 / 回歸目標)或 RL reward |
| 3 | **模型** | `jimq_research.export.baseline.train_baseline_stub` | 你的真模型(序列模型 / RL policy / 多模態)。只要產出物件有 `predict(features_dict)->signal` 介面即可 |
| 4 | **推論特徵** | `jimq_engine.strategies.model_inference.ModelInferenceStrategy._build_features` | 與替換點 1 **同一組特徵**(再次強調反 skew);建議把特徵函式抽成兩端共用 |
| 5 | **訊號語意** | `ModelInferenceStrategy._signal_to_action` | 你模型輸出的真正語意(機率閾值 / 回歸值 / RL 離散動作 id) |

每處在程式裡都有 `USER REPLACEMENT POINT` 標記註解。換掉這 5 點即得到真策略,
而 register→backtest→MLflow 的整條研究迴圈不需重寫。

---

## 8. 收尾 / 清理

```bash
# 清掉本機 demo 登錄的 stub 列(選用;data/ 為 gitignore):
cd /home/jacc/projects/JimQ/research
uv run python -c "
from sqlalchemy import create_engine, text
from jimq_research.training.store import local_engine_url
e=create_engine(local_engine_url())
with e.begin() as c:
    c.execute(text(\"delete from model_registry where name='baseline-stub'\"))
print('cleaned stub rows')
"

# 停 MLflow docker 服務(若有啟):
docker compose --profile research down
```
```
