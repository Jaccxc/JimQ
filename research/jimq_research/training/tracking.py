"""卡 #16 — MLflow 實驗追蹤薄 wrapper。

提供 ``with track_run(experiment, params): log_metrics(...)`` 的薄介面,把實驗
追蹤的細節(tracking server 位址、experiment 解析、run 生命週期)收斂在一處,
其餘程式(批量 backtest runner、未來的訓練迴圈)只看到極小的 public surface。

設計要點:
- **tracking URI 解析**:呼叫端可顯式傳 ``tracking_uri``;否則讀 ``MLFLOW_TRACKING_URI``
  環境變數(指向 docker MLflow 服務,如 ``http://localhost:5000``);兩者皆無時退回
  本地 sqlite(``data/mlflow/mlflow.db``,對齊 docker 服務 backend 型別)。MLflow 3.x
  已停用檔案 store,故一律走 sqlite/http,絕不用 file store。
- **薄**:本模組不擁有指標計算或策略知識,只轉呼叫 MLflow fluent API;params/metrics/
  artifacts 由呼叫端提供。
- **離線可測**:傳本地 sqlite URI 即可在無 docker / 無網路下記錄並由 MlflowClient 查回。
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import mlflow

# 本地預設 backend(對齊 docker 服務:sqlite backend store + 本地 artifact 目錄)。
_DEFAULT_DATA_DIR = Path(
    os.environ.get("JIMQ_MLFLOW_DIR", "data/mlflow")
)


def resolve_tracking_uri(tracking_uri: str | None = None) -> str:
    """決定 MLflow tracking URI(顯式 > 環境變數 > 本地 sqlite 退路)。"""
    if tracking_uri:
        return tracking_uri
    env = os.environ.get("MLFLOW_TRACKING_URI")
    if env:
        return env
    db = _DEFAULT_DATA_DIR / "mlflow.db"
    return f"sqlite:///{db}"


def _ensure_experiment(
    experiment: str,
    *,
    tracking_uri: str,
    artifact_location: str | None,
) -> str:
    """取得(或建立)experiment,回傳其 id。建立時可指定 artifact 根位置。"""
    mlflow.set_tracking_uri(tracking_uri)
    existing = mlflow.get_experiment_by_name(experiment)
    if existing is not None:
        return existing.experiment_id
    return mlflow.create_experiment(experiment, artifact_location=artifact_location)


@contextmanager
def track_run(
    experiment: str,
    params: Mapping[str, Any] | None = None,
    *,
    tracking_uri: str | None = None,
    artifact_location: str | None = None,
    run_name: str | None = None,
    tags: Mapping[str, Any] | None = None,
) -> Iterator[str]:
    """在 ``experiment`` 下開一個 MLflow run,進場記錄 ``params``。

    yield 出 ``run_id``(字串);區塊內可呼叫 ``log_metrics`` / ``log_artifacts``。
    區塊正常或例外離場時 run 都會被妥善結束。
    """
    uri = resolve_tracking_uri(tracking_uri)
    exp_id = _ensure_experiment(
        experiment, tracking_uri=uri, artifact_location=artifact_location
    )
    mlflow.set_tracking_uri(uri)
    with mlflow.start_run(
        experiment_id=exp_id, run_name=run_name, tags=dict(tags) if tags else None
    ) as run:
        if params:
            mlflow.log_params(dict(params))
        yield run.info.run_id


def log_metrics(
    metrics: Mapping[str, float],
    *,
    tracking_uri: str | None = None,
    step: int | None = None,
) -> None:
    """記錄一組數值 metrics 到當前 active run(僅轉呼叫 MLflow)。"""
    mlflow.set_tracking_uri(resolve_tracking_uri(tracking_uri))
    mlflow.log_metrics({k: float(v) for k, v in metrics.items()}, step=step)


def log_params(
    params: Mapping[str, Any],
    *,
    tracking_uri: str | None = None,
) -> None:
    """記錄一組 params 到當前 active run(僅轉呼叫 MLflow)。"""
    mlflow.set_tracking_uri(resolve_tracking_uri(tracking_uri))
    mlflow.log_params(dict(params))


def log_artifacts(
    paths: Sequence[str],
    *,
    tracking_uri: str | None = None,
    artifact_path: str | None = None,
) -> None:
    """把本地檔案逐一以 artifact 記錄到當前 active run。"""
    mlflow.set_tracking_uri(resolve_tracking_uri(tracking_uri))
    for p in paths:
        mlflow.log_artifact(p, artifact_path=artifact_path)
