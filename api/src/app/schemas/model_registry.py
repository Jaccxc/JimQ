"""Pydantic schemas for ``model_registry`` (卡 #17; modelled on backtest_run)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.model_registry import ModelFramework


class ModelRegistryBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=128, examples=["ppo_btc_perp"])]
    version: Annotated[str, Field(min_length=1, max_length=64, examples=["v1"])]
    artifact_path: Annotated[
        str, Field(min_length=1, max_length=512, examples=["data/models/ppo_btc_perp/v1"])
    ]
    framework: ModelFramework
    training_run_id: Annotated[
        str | None, Field(default=None, max_length=64, examples=["grid-abc-007"])
    ] = None
    sharpe: Decimal | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class ModelRegistryCreate(ModelRegistryBase):
    model_config = ConfigDict(extra="forbid")


class ModelRegistryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_path: Annotated[str | None, Field(default=None, max_length=512)] = None
    training_run_id: Annotated[str | None, Field(default=None, max_length=64)] = None
    sharpe: Decimal | None = None
    metrics: dict[str, Any] | None = None


class ModelRegistryRead(ModelRegistryBase):
    id: int
    created_at: datetime
