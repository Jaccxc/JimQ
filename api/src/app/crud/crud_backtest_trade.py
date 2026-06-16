"""FastCRUD instance for ``backtest_trade`` (卡 #21 W2)."""

from fastcrud import FastCRUD

from ..models.backtest_trade import BacktestTrade
from ..schemas.backtest_trade import BacktestTradeCreate, BacktestTradeRead

CRUDBacktestTrade = FastCRUD[
    BacktestTrade,
    BacktestTradeCreate,
    BacktestTradeCreate,
    BacktestTradeCreate,
    BacktestTradeRead,
    BacktestTradeRead,
]
crud_backtest_trades = CRUDBacktestTrade(BacktestTrade)
