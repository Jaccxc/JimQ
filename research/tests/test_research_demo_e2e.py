"""卡 #18 — 端到端研究 demo 整合測試。

驗證完整研究迴圈可跑通(行為層,不驗實作細節):
dataset → train stub → (artifact 落地)→ model 驅動 backtest 產生成交 → MLflow 有 run。

用合成 catalog(震盪價格,確保標籤兩類且 backtest 會成交)+ tmp models_root +
本地 sqlite MLflow URI,離線可測;略過 Postgres 登錄(register=False),登錄路徑
另由 model_registry round-trip 測試覆蓋。
"""

from __future__ import annotations

import math

import mlflow
import polars as pl
from mlflow.tracking import MlflowClient

from jimq_engine.catalog.ingest import BAR_TYPE_1M, ingest_bars
from jimq_engine.catalog.instruments import btcusdt_perp_binance
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from jimq_research.training.run_research_demo import run_demo

_BASE_MS = 1_700_000_000_000


def _oscillating_klines(n: int = 300):
    """震盪價格(正弦 + 緩升):製造方向兩類標籤,且足以觸發 bracket 成交。"""
    klines = []
    for i in range(n):
        price = 40000.0 + 800.0 * math.sin(i / 6.0) + i * 2.0
        o = price
        c = 40000.0 + 800.0 * math.sin((i + 1) / 6.0) + (i + 1) * 2.0
        hi = max(o, c) + 30
        lo = min(o, c) - 30
        ts = _BASE_MS + i * 60_000
        klines.append(
            [ts, f"{o}", f"{hi}", f"{lo}", f"{c}", f"{10 + i % 5}.000",
             ts + 59_999, "0", 1, "0", "0", "0"]
        )
    return klines


def _make_catalog(tmp_path) -> ParquetDataCatalog:
    catalog = ParquetDataCatalog(path=str(tmp_path / "catalog"))
    instrument = btcusdt_perp_binance()
    catalog.write_data([instrument])
    ingest_bars(catalog, _oscillating_klines(), instrument)
    return catalog


def test_demo_end_to_end_produces_fills_and_mlflow_run(tmp_path):
    catalog = _make_catalog(tmp_path)
    mlflow_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"

    result = run_demo(
        register=False,          # Postgres 登錄另測;此處離線端到端
        mlflow=True,
        models_root=tmp_path / "models",
        model_name="baseline-stub",
        mlflow_experiment="research-demo-test",
        catalog=catalog,
        mlflow_tracking_uri=mlflow_uri,
    )

    # 1. dataset 有資料。
    assert result["dataset_rows"] > 0

    # 2. artifact 落地(對齊 ModelStore 磁碟慣例)。
    from pathlib import Path

    artifact = Path(result["artifact_dir"])
    assert artifact.is_dir()
    assert any(artifact.iterdir())

    # 3. model 驅動 backtest 確實送單並成交(plumbing 通,非 alpha)。
    assert result["num_orders"] > 0, "模型推論應驅動下單"
    assert result["num_fills"] > 0, "bracket 進場應有成交"

    # 4. MLflow 有對應 run,且記了 metrics。
    assert result["mlflow_run_id"] is not None
    mlflow.set_tracking_uri(mlflow_uri)
    client = MlflowClient(tracking_uri=mlflow_uri)
    run = client.get_run(result["mlflow_run_id"])
    assert run.data.metrics["num_orders"] == float(result["num_orders"])
    assert run.data.metrics["num_fills"] == float(result["num_fills"])
    assert run.data.metrics["dataset_rows"] == float(result["dataset_rows"])
