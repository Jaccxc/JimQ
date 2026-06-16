"""Pydantic schemas for ``backtest_trade`` (卡 #21 W2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..models.backtest_trade import TradeSide


class BacktestTradeBase(BaseModel):
    run_id: Annotated[int, Field(examples=[42])]
    instrument_id: Annotated[
        str, Field(min_length=1, max_length=64, examples=["BTCUSDT-PERP.BINANCE"])
    ]
    side: TradeSide
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    sl: Decimal | None = None
    tp: Decimal | None = None
    pnl: Decimal | None = None
    opened_at: datetime
    closed_at: datetime


class BacktestTradeCreate(BacktestTradeBase):
    model_config = ConfigDict(extra="forbid")


class BacktestTradeRead(BacktestTradeBase):
    id: int
