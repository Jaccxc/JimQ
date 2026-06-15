"""backtests resource router (FastCRUD auto-endpoints, no auth — auth stripped)."""

from fastcrud import crud_router

from ...core.db.database import async_get_db
from ...crud.crud_backtest_run import crud_backtest_runs
from ...models.backtest_run import BacktestRun
from ...schemas.backtest_run import BacktestRunCreate, BacktestRunRead, BacktestRunUpdate

router = crud_router(
    session=async_get_db,
    model=BacktestRun,
    crud=crud_backtest_runs,
    create_schema=BacktestRunCreate,
    update_schema=BacktestRunUpdate,
    select_schema=BacktestRunRead,
    path="/backtests",
    tags=["backtests"],
)
