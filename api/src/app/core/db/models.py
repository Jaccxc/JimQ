"""Shared declarative model mixins.

Trimmed from boilerplate v0.15.0: dropped ``UUIDMixin`` / ``SoftDeleteMixin``
(user/post oriented). Kept a timezone-aware ``TimestampMixin`` — all JimQ
timestamps are ``timestamptz`` (DEV_CONTRACT_AFK 鐵律 10).
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        onupdate=lambda: datetime.now(UTC),
    )
