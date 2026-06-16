"""Pydantic schemas for ``backtest_run`` (modelled on the boilerplate post template)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.backtest_run import BacktestStatus


class BacktestRunBase(BaseModel):
    strategy_name: Annotated[str, Field(min_length=1, max_length=128, examples=["ema_cross"])]
    instrument_id: Annotated[str, Field(min_length=1, max_length=64, examples=["BTCUSDT-PERP.BINANCE"])]
    bar_type: Annotated[str, Field(min_length=1, max_length=128)]
    timeframe: Annotated[str, Field(min_length=1, max_length=32, examples=["1H"])]
    start_time: datetime
    end_time: datetime
    params: dict[str, Any] = Field(default_factory=dict)
    run_group: Annotated[str | None, Field(default=None, max_length=64, examples=["grid-abc"])] = None
    correlation_id: Annotated[str | None, Field(default=None, max_length=64, examples=["corr-abc"])] = None


class BacktestRunCreate(BacktestRunBase):
    model_config = ConfigDict(extra="forbid")


class BacktestRunUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BacktestStatus | None = None
    total_return: Decimal | None = None
    sharpe: Decimal | None = None
    max_drawdown: Decimal | None = None
    num_trades: int | None = None
    final_balance: Decimal | None = None


class BacktestRunRead(BacktestRunBase):
    id: int
    status: BacktestStatus
    total_return: Decimal | None = None
    sharpe: Decimal | None = None
    max_drawdown: Decimal | None = None
    num_trades: int | None = None
    final_balance: Decimal | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BacktestRunRequest(BaseModel):
    """卡 #20 (W1) — 從 UI launcher 觸發一次 backtest 的請求 body。

    刻意只收使用者層欄位(symbol/timeframe/strategy/params/start/end);
    bar_type 由 symbol+timeframe 在伺服端推導,status/id/correlation_id 由
    伺服端產生。
    """

    model_config = ConfigDict(extra="forbid")

    symbol: Annotated[str, Field(min_length=1, max_length=64, examples=["BTCUSDT-PERP.BINANCE"])]
    timeframe: Annotated[str, Field(min_length=1, max_length=32, examples=["1m"])]
    strategy: Annotated[str, Field(min_length=1, max_length=128, examples=["ema_cross"])]
    params: dict[str, Any] = Field(default_factory=dict)
    start: datetime
    end: datetime


class BacktestRunAccepted(BaseModel):
    """POST /backtests/run 的回應:run 已建立(PENDING)、命令已發布。"""

    run_id: int
    correlation_id: str
    status: BacktestStatus
