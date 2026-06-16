"""卡 #20 (W1) — backtest_run 狀態回寫(app 級 SQLAlchemy)。

command worker 跑 backtest 期間以 app 級 SQLAlchemy(非手動 psql;鐵律 2 精神)
更新 ``backtest_run`` 的 status 流轉(PENDING → RUNNING → COMPLETED / FAILED)
與結果指標。

設計(本地決策):
- engine 不 import api 套件(避免反向耦合 + 帶入 FastAPI 依賴);此處用
  **SQLAlchemy Core** 對 ``backtest_run`` 表下精準的 ``UPDATE``,欄位契約與 api
  model 對齊(status VARCHAR、NUMERIC 指標)。仍是「app 級 SQLAlchemy 寫入」,
  非手動 DDL/DML(鐵律 2 / 3)。
- status 以 VARCHAR 大寫字面值寫入(鐵律 11;與 BacktestStatus 契約一致)。
- 只連 localhost(鐵律 4);DSN 由 env 組,預設 localhost。
- async engine 生命週期由 worker 持有,跑完 ``aclose()``。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# backtest_run 表的輕量 Core 定義(欄位契約對齊 api model;只用到需更新的欄位)。
_metadata = sa.MetaData()
backtest_run_table = sa.Table(
    "backtest_run",
    _metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("status", sa.String(32)),
    sa.Column("total_return", sa.Numeric(20, 8)),
    sa.Column("sharpe", sa.Numeric(20, 8)),
    sa.Column("max_drawdown", sa.Numeric(20, 8)),
    sa.Column("num_trades", sa.BigInteger),
    sa.Column("final_balance", sa.Numeric(30, 8)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

# status 契約字面值(對齊 api BacktestStatus;鐵律 11)。
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"

# 允許更新的結果指標欄位(白名單,避免任意欄位注入)。
_METRIC_COLUMNS = ("total_return", "sharpe", "max_drawdown", "num_trades", "final_balance")


def backtest_run_db_url(env: Mapping[str, str] | None = None) -> str:
    """由 env 組 backtest_run 的 async SQLAlchemy DSN(預設 localhost;鐵律 4)。

    優先用顯式 ``DATABASE_URL``(若已是 asyncpg DSN);否則由 ``POSTGRES_*`` 組。
    """
    import os

    env = os.environ if env is None else env
    explicit = env.get("DATABASE_URL")
    if explicit and "+asyncpg" in explicit:
        return explicit
    user = env.get("POSTGRES_USER", "postgres")
    password = env.get("POSTGRES_PASSWORD", "1234")
    host = env.get("POSTGRES_HOST", "localhost")
    port = env.get("POSTGRES_PORT", "5432")
    db = env.get("POSTGRES_DB", "jimq")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


class StatusWriter:
    """以 app 級 SQLAlchemy 更新 backtest_run 狀態 / 指標。"""

    def __init__(self, db_url: str, *, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or create_async_engine(db_url)

    async def _update(self, run_id: int, values: dict[str, Any]) -> None:
        values = {**values, "updated_at": datetime.now(UTC)}
        stmt = (
            sa.update(backtest_run_table)
            .where(backtest_run_table.c.id == run_id)
            .values(**values)
        )
        async with self._engine.begin() as conn:
            await conn.execute(stmt)

    async def mark_running(self, run_id: int) -> None:
        """status -> RUNNING(backtest 開跑)。"""
        await self._update(run_id, {"status": STATUS_RUNNING})

    async def mark_completed(
        self, run_id: int, *, metrics: Mapping[str, Any] | None = None
    ) -> None:
        """status -> COMPLETED,並寫入白名單內的結果指標(Decimal/int)。"""
        values: dict[str, Any] = {"status": STATUS_COMPLETED}
        for col in _METRIC_COLUMNS:
            if metrics and col in metrics and metrics[col] is not None:
                raw = metrics[col]
                values[col] = raw if isinstance(raw, (int, Decimal)) else Decimal(str(raw))
        await self._update(run_id, values)

    async def mark_failed(self, run_id: int) -> None:
        """status -> FAILED(backtest 例外)。"""
        await self._update(run_id, {"status": STATUS_FAILED})

    async def aclose(self) -> None:
        await self._engine.dispose()
