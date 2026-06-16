"""卡 #23 (W4) — MLflow 讀取 proxy 端點(研究儀表板用)。

api 經 **HTTP** 連 MLflow tracking server 的 REST API
(``<MLFLOW_TRACKING_URI>/api/2.0/mlflow/...``),把 experiments / runs 攤平成前端
易吃的形狀回出。

設計(本地決策):
- **不 import ``mlflow``**:api 保持精簡(research 為獨立 venv);只用 httpx 打 REST
  API。對齊卡 body 設計指引「MLflow 讀取端點在 api(api 可連 mlflow http,不需
  import research)」。
- **注入 HTTP client**:``get_mlflow_http`` 依賴回 async httpx client,測試可 override
  成 fake(不需真 MLflow 服務)。
- **攤平**:MLflow REST 的 ``params`` / ``metrics`` 是 list-of-{key,value};這裡攤成
  ``dict`` 讓 web 直接比較/表格化。
- **localhost only**(鐵律 4):預設 tracking URI 指 docker research profile 的
  localhost:5000。
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query

from ...core.config import settings

router = APIRouter(prefix="/mlflow", tags=["mlflow"])


def _rest_base() -> str:
    """MLflow REST API 根(``<tracking_uri>/api/2.0/mlflow``,去尾斜線)。"""
    return settings.MLFLOW_TRACKING_URI.rstrip("/") + "/api/2.0/mlflow"


def get_mlflow_http() -> Any:
    """注入 async HTTP client(httpx;測試可 override 成 fake)。"""
    return httpx.AsyncClient(timeout=10.0)


def _flatten(pairs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """MLflow REST 的 [{"key":..,"value":..}, ...] → {key: value}。"""
    return {p["key"]: p["value"] for p in (pairs or [])}


@router.get(
    "/experiments",
    summary="列出 MLflow experiments(代理 MLflow REST experiments/search)",
)
async def list_experiments(client=Depends(get_mlflow_http)) -> list[dict[str, Any]]:
    """回 [{experiment_id, name, lifecycle_stage, ...}]。"""
    try:
        resp = await client.post(
            f"{_rest_base()}/experiments/search", json={"max_results": 1000}
        )
        resp.raise_for_status()
        return resp.json().get("experiments", [])
    finally:
        await client.aclose()


@router.get(
    "/runs",
    summary="列出某 experiment 的 runs(params/metrics 攤平;代理 runs/search)",
)
async def list_runs(
    experiment_id: str = Query(..., description="MLflow experiment id"),
    client=Depends(get_mlflow_http),
) -> list[dict[str, Any]]:
    """回攤平後的 [{run_id, run_name, status, start_time, params:{}, metrics:{}}]。"""
    try:
        resp = await client.post(
            f"{_rest_base()}/runs/search",
            json={"experiment_ids": [experiment_id], "max_results": 1000},
        )
        resp.raise_for_status()
        runs = resp.json().get("runs", [])
    finally:
        await client.aclose()

    out: list[dict[str, Any]] = []
    for run in runs:
        info = run.get("info", {})
        data = run.get("data", {})
        out.append(
            {
                "run_id": info.get("run_id"),
                "run_name": info.get("run_name"),
                "experiment_id": info.get("experiment_id"),
                "status": info.get("status"),
                "start_time": info.get("start_time"),
                "params": _flatten(data.get("params")),
                "metrics": _flatten(data.get("metrics")),
            }
        )
    return out
