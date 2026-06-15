"""卡 #18 — 端到端研究 demo:完整研究迴圈一次跑通。

串起所有既有元件(不重造輪子):

  1. dataset builder(#14)  : catalog → jimq_core.features → 特徵/標籤資料集。
  2. train stub(#18)       : 訓練佔位 baseline 模型(USER REPLACEMENT POINT)。
  3. register(#17)         : artifact 存 data/models/<name>/<version>/ + metadata
                             進 Postgres model_registry。
  4. model 驅動 backtest(#18+#4): 從 registry 取回 artifact、用通用
                             ModelInferenceStrategy 在 on_bar 以 jimq_core.features
                             算與訓練同一份特徵(反 train/serve skew)推論下單。
  5. MLflow(#16)          : 結果記成一個 run。

stub 的重點是證明 PLUMBING 通,不是 alpha。真模型 / 真特徵 / 真標籤 / 真獎勵的
替換點見:
  - 本檔的 build_demo_dataset()(特徵/標籤注入點);
  - jimq_research.export.baseline.train_baseline_stub()(模型);
  - jimq_engine.strategies.model_inference.ModelInferenceStrategy(特徵/訊號);
  - runbook:docs/runbooks/20260616-research-demo.md。

用法(在 research/ 的 venv):
    uv run python -m jimq_research.training.run_research_demo
    uv run python -m jimq_research.training.run_research_demo --no-mlflow --no-register
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl

from jimq_engine.catalog.ingest import BAR_TYPE_1M, open_catalog, query_bars
from jimq_engine.catalog.instruments import (
    BTCUSDT_PERP_BINANCE_ID,
    btcusdt_perp_binance,
)
from jimq_engine.nodes.backtest import build_engine_with_strategy
from jimq_engine.strategies.model_inference import (
    ModelInferenceConfig,
    ModelInferenceStrategy,
)

from jimq_research.data import build_dataset, ema_feature
from jimq_research.export import (
    load_model_artifact,
    save_model_artifact,
    train_baseline_stub,
)
from jimq_research.training import summarize_engine
from jimq_research.training.model_registry import register_model
from jimq_research.training.tracking import log_metrics, log_params, track_run

# 示範特徵週期 —— 訓練資料集與推論策略**必須一致**(否則 train/serve skew)。
FAST_PERIOD = 10
SLOW_PERIOD = 20
FEATURE_COLS = ["ema_fast", "ema_slow"]
LABEL_COL = "label_up"

# 預設 artifact 根:repo 根 data/models(對齊 api ModelStore;gitignored)。
_DEFAULT_MODELS_ROOT = (
    Path(__file__).resolve().parents[3] / "data" / "models"
)


def _next_up_label(frame: pl.DataFrame) -> pl.Series:
    """USER REPLACEMENT POINT(標籤):下一根 close 是否高於本根(二元)。

    換成你的真標籤(多分類 / 回歸目標 / RL 不需要標籤而用獎勵)。最後一根無
    next bar → null,訓練時會被 drop。
    """
    nxt = frame["close"].shift(-1)
    return (nxt > frame["close"]).cast(pl.Int8).alias(LABEL_COL)


def build_demo_dataset(catalog, *, start=None, end=None) -> pl.DataFrame:
    """USER REPLACEMENT POINT(特徵/標籤注入):建 demo 資料集。

    特徵 = 兩條 EMA(復用 jimq_core.features,與 ModelInferenceStrategy 推論同碼);
    標籤 = 下一根方向。換成你的真特徵組合與標籤即可,plumbing 不變。
    """
    return build_dataset(
        catalog,
        bar_type=BAR_TYPE_1M,
        start=start,
        end=end,
        feature_fns=[
            ema_feature(period=FAST_PERIOD, source="close", name="ema_fast"),
            ema_feature(period=SLOW_PERIOD, source="close", name="ema_slow"),
        ],
        label_fn=_next_up_label,
    )


def run_demo(
    *,
    register: bool = True,
    mlflow: bool = True,
    models_root: Path = _DEFAULT_MODELS_ROOT,
    model_name: str = "baseline-stub",
    model_version: str | None = None,
    mlflow_experiment: str = "research-demo",
    catalog=None,
    mlflow_tracking_uri: str | None = None,
) -> dict:
    """跑完整研究迴圈,回傳結果摘要 dict(供腳本印出 / 測試斷言)。

    ``catalog`` 預設取共享 ParquetDataCatalog(``open_catalog``);測試可注入
    合成 catalog。``mlflow_tracking_uri`` 可顯式指定(測試用本地 sqlite),
    None 時走 tracking wrapper 的解析(env > 本地 sqlite 退路)。
    """
    version = model_version or f"v-{uuid.uuid4().hex[:8]}"
    if catalog is None:
        catalog = open_catalog()

    # --- 1. dataset(catalog → 特徵/標籤)---
    dataset = build_demo_dataset(catalog)

    # --- 2. train stub(USER REPLACEMENT POINT)---
    model = train_baseline_stub(
        dataset, feature_cols=FEATURE_COLS, label_col=LABEL_COL
    )

    # --- 3. register(artifact 存 data/models + metadata 進 Postgres)---
    artifact_dir = save_model_artifact(
        model, name=model_name, version=version, models_root=models_root
    )
    registry_id = None
    if register:
        registry_id = register_model(
            name=model_name,
            version=version,
            artifact_path=str(artifact_dir),
            framework="SKLEARN",
            metrics={"n_features": len(FEATURE_COLS), "stub": True},
        )

    # --- 4. model 驅動 backtest(從 registry/artifact 取回模型,通用策略推論)---
    loaded = load_model_artifact(artifact_dir)
    bars = query_bars(catalog, bar_type=BAR_TYPE_1M)
    if not bars:
        raise ValueError("catalog 無 1m bars;先 ingest(scripts/ingest)。")
    instrument = btcusdt_perp_binance()
    config = ModelInferenceConfig(
        instrument_id=BTCUSDT_PERP_BINANCE_ID,
        bar_type=BAR_TYPE_1M,
        fast_period=FAST_PERIOD,
        slow_period=SLOW_PERIOD,
        trade_size=Decimal("0.100"),
        sl_pct=Decimal("0.01"),
        tp_pct=Decimal("0.02"),
    )
    strategy = ModelInferenceStrategy(config=config, model=loaded)
    engine = build_engine_with_strategy(instrument, bars, strategy)

    try:
        ns = 1_000_000_000
        summary = summarize_engine(
            engine,
            strategy_name="model_inference",
            instrument_id=str(BTCUSDT_PERP_BINANCE_ID),
            bar_type=str(BAR_TYPE_1M),
            timeframe="1m",
            start_time=datetime.fromtimestamp(bars[0].ts_init / ns, tz=UTC),
            end_time=datetime.fromtimestamp(bars[-1].ts_init / ns, tz=UTC),
            params={
                "model_name": model_name,
                "model_version": version,
                "fast_period": FAST_PERIOD,
                "slow_period": SLOW_PERIOD,
            },
        )
        num_orders = len(engine.cache.orders())
        num_fills = sum(o.filled_qty > 0 for o in engine.cache.orders())
    finally:
        engine.dispose()

    # --- 5. MLflow(結果記成一個 run)---
    mlflow_run_id = None
    if mlflow:
        with track_run(
            mlflow_experiment,
            {
                "model_name": model_name,
                "model_version": version,
                "framework": "SKLEARN",
                "fast_period": FAST_PERIOD,
                "slow_period": SLOW_PERIOD,
            },
            run_name=f"demo-{version}",
            tracking_uri=mlflow_tracking_uri,
        ) as run_id:
            mlflow_run_id = run_id
            metrics = {
                "dataset_rows": float(dataset.height),
                "num_orders": float(num_orders),
                "num_fills": float(num_fills),
                "num_trades": float(summary.num_trades or 0),
                "total_return": float(summary.total_return or 0),
                "final_balance": float(summary.final_balance or 0),
            }
            log_metrics(metrics, tracking_uri=mlflow_tracking_uri)
            log_params({"registry_id": registry_id}, tracking_uri=mlflow_tracking_uri)

    return {
        "dataset_rows": dataset.height,
        "model_name": model_name,
        "model_version": version,
        "artifact_dir": str(artifact_dir),
        "registry_id": registry_id,
        "num_orders": num_orders,
        "num_fills": num_fills,
        "num_trades": summary.num_trades,
        "total_return": summary.total_return,
        "final_balance": summary.final_balance,
        "mlflow_run_id": mlflow_run_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="端到端研究 demo:dataset→train stub→register→model backtest→MLflow"
    )
    parser.add_argument("--no-register", action="store_true", help="略過 Postgres 登錄")
    parser.add_argument("--no-mlflow", action="store_true", help="略過 MLflow 記錄")
    parser.add_argument("--model-name", default="baseline-stub")
    parser.add_argument("--mlflow-experiment", default="research-demo")
    args = parser.parse_args()

    result = run_demo(
        register=not args.no_register,
        mlflow=not args.no_mlflow,
        model_name=args.model_name,
        mlflow_experiment=args.mlflow_experiment,
    )

    print("\n=== RESEARCH DEMO RESULT ===")
    for k, v in result.items():
        print(f"{k:>16}: {v}")
    print(
        "\nNOTE: stub baseline 只證明 plumbing(dataset→train→register→model "
        "backtest→MLflow),非 alpha。替換點見 runbook 與程式註解。"
    )


if __name__ == "__main__":
    main()
