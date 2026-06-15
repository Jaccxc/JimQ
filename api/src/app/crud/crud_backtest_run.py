"""FastCRUD instance for ``backtest_run`` (sticks to the boilerplate posts pattern)."""

from fastcrud import FastCRUD

from ..models.backtest_run import BacktestRun
from ..schemas.backtest_run import BacktestRunCreate, BacktestRunRead, BacktestRunUpdate

CRUDBacktestRun = FastCRUD[
    BacktestRun,
    BacktestRunCreate,
    BacktestRunUpdate,
    BacktestRunUpdate,
    BacktestRunRead,
    BacktestRunRead,
]
crud_backtest_runs = CRUDBacktestRun(BacktestRun)
