"""卡 #16 — MLflow 實驗追蹤薄 wrapper(行為驗證,離線 sqlite backend)。

透過 public interface 驗證 wrapper 行為,不對 docker MLflow 服務硬依賴:
- ``track_run(experiment, params, tracking_uri=...)`` context manager 起一個 MLflow
  run,進場記錄 params;區塊內可 ``log_metrics`` / ``log_artifacts``。
- 離場後可由 MLflow API(``MlflowClient``)依 run_id 查回 params 與 metrics。
- MLflow 3.x 檔案 store 已停用,backend 一律用 sqlite(對齊 docker 服務 backend);
  測試用臨時 sqlite + 本地 artifact 目錄,純離線、不打網路、不需 docker。

MLflow 把 params 以字串存,故比對 params 用字串值。
"""

from __future__ import annotations

from mlflow.tracking import MlflowClient


def _local_uri(tmp_path) -> tuple[str, str]:
    db = tmp_path / "mlflow.db"
    art = tmp_path / "artifacts"
    return f"sqlite:///{db}", f"file://{art}"


def test_track_run_logs_params_and_metrics_queryable_via_api(tmp_path):
    from jimq_research.training.tracking import log_metrics, track_run

    uri, art = _local_uri(tmp_path)
    exp = "unit-exp"
    params = {"fast_period": 3, "slow_period": 8}

    with track_run(
        exp, params, tracking_uri=uri, artifact_location=art, run_name="r1"
    ) as run_id:
        log_metrics({"total_return": 0.012, "sharpe": 1.25}, tracking_uri=uri)

    assert isinstance(run_id, str) and run_id

    client = MlflowClient(tracking_uri=uri)
    fetched = client.get_run(run_id)
    # params 以字串查回(MLflow 行為)。
    assert fetched.data.params["fast_period"] == "3"
    assert fetched.data.params["slow_period"] == "8"
    assert fetched.data.metrics["total_return"] == 0.012
    assert fetched.data.metrics["sharpe"] == 1.25
    # run 掛在指定 experiment 下。
    experiment = client.get_experiment(fetched.info.experiment_id)
    assert experiment.name == exp


def test_track_run_logs_artifacts(tmp_path):
    from jimq_research.training.tracking import log_artifacts, track_run

    uri, art = _local_uri(tmp_path)
    note = tmp_path / "note.txt"
    note.write_text("metrics summary")

    with track_run(
        "art-exp", {"k": 1}, tracking_uri=uri, artifact_location=art
    ) as run_id:
        log_artifacts([str(note)], tracking_uri=uri)

    client = MlflowClient(tracking_uri=uri)
    paths = [a.path for a in client.list_artifacts(run_id)]
    assert "note.txt" in paths
