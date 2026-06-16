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
