"""Shared Pydantic schema mixins (trimmed from boilerplate v0.15.0).

Dropped Token / TokenBlacklist / UUID / PersistentDeletion schemas (auth & soft
delete removed). Kept ``HealthCheck`` and a timezone-aware ``TimestampSchema``.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer


class HealthCheck(BaseModel):
    name: str
    version: str
    description: str | None = None


class TimestampSchema(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime | None = Field(default=None)

    @field_serializer("created_at")
    def serialize_created_at(self, created_at: datetime | None, _info: Any) -> str | None:
        return created_at.isoformat() if created_at is not None else None

    @field_serializer("updated_at")
    def serialize_updated_at(self, updated_at: datetime | None, _info: Any) -> str | None:
        return updated_at.isoformat() if updated_at is not None else None
