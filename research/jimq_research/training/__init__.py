"""training — Stable-Baselines3 + MLflow training loops + batch backtest runner.

卡 #15:批量 backtest runner(``run_grid`` / ``run_single``)對策略參數網格復用
engine 的 BacktestNode 跑 backtest,產出共用 ``BacktestRunSummary``。
"""

from jimq_research.training.batch_backtest import (
    expand_grid,
    run_grid,
    run_single,
    summarize_engine,
)
from jimq_research.training.store import (
    delete_run_group,
    local_engine_url,
    persist_summaries,
    query_runs,
)

__all__ = [
    "expand_grid",
    "run_grid",
    "run_single",
    "summarize_engine",
    "delete_run_group",
    "local_engine_url",
    "persist_summaries",
    "query_runs",
]
