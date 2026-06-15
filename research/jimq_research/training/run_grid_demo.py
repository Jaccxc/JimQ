"""卡 #15 — 批量 backtest runner 可執行 demo。

對 EMA 策略的小參數網格(fast x slow)在共用 ParquetDataCatalog(預設 data/catalog,
或 ``JIMQ_CATALOG_PATH``)上批量跑 backtest,把每組 run 摘要持久化到 localhost
Postgres ``backtest_run``(同一 ``run_group`` 標記),再查回印出比較表。

用法(在 research/ 的 venv):
    uv run python -m jimq_research.training.run_grid_demo
    uv run python -m jimq_research.training.run_grid_demo --fast 3 5 --slow 8 13
"""

from __future__ import annotations

import argparse
import uuid

from jimq_engine.catalog.ingest import BAR_TYPE_1M, open_catalog

from jimq_research.training import (
    local_engine_url,
    persist_summaries,
    query_runs,
    run_grid,
    track_summaries,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="EMA param-grid batch backtest -> Postgres")
    parser.add_argument("--fast", type=int, nargs="+", default=[3, 5])
    parser.add_argument("--slow", type=int, nargs="+", default=[8, 13])
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--run-group", default=None, help="預設自動產生唯一標記")
    parser.add_argument(
        "--mlflow-experiment",
        default="backtest",
        help="記錄到的 MLflow experiment 名稱(tracking URI 取 MLFLOW_TRACKING_URI,"
        "未設則退回本地 sqlite data/mlflow/mlflow.db)",
    )
    parser.add_argument(
        "--no-mlflow", action="store_true", help="略過 MLflow 記錄"
    )
    args = parser.parse_args()

    run_group = args.run_group or f"grid-{uuid.uuid4().hex[:8]}"
    catalog = open_catalog()

    summaries = run_grid(
        catalog,
        param_grid={"fast_period": args.fast, "slow_period": args.slow},
        bar_type=BAR_TYPE_1M,
        timeframe=args.timeframe,
        run_group=run_group,
    )
    # EMA 需 fast < slow;略過不合法組合(策略 __init__ 會擋,這裡先濾掉)。
    print(f"run_group={run_group}  combos={len(summaries)}")

    url = local_engine_url()
    ids = persist_summaries(summaries, engine_url=url)
    print(f"persisted {len(ids)} runs ids={ids}")

    # 每組參數同時記錄成一個 MLflow run(params=策略參數,metrics=績效)。
    if not args.no_mlflow:
        run_ids = track_summaries(summaries, experiment=args.mlflow_experiment)
        print(f"logged {len(run_ids)} MLflow runs to experiment={args.mlflow_experiment!r}")

    rows = query_runs(url, run_group=run_group)
    print("\n=== COMPARISON ===")
    print(f"{'fast':>4} {'slow':>4} {'trades':>6} {'return':>12} {'sharpe':>10} {'maxDD':>10} {'final_balance':>18}")
    for r in sorted(rows, key=lambda x: (x["params"]["fast_period"], x["params"]["slow_period"])):
        p = r["params"]
        print(
            f"{p['fast_period']:>4} {p['slow_period']:>4} {r['num_trades']:>6} "
            f"{str(r['total_return']):>12} {str(r['sharpe']):>10} "
            f"{str(r['max_drawdown']):>10} {str(r['final_balance']):>18}"
        )


if __name__ == "__main__":
    main()
