"""卡 #15 — 把 BacktestRunSummary 持久化到 Postgres ``backtest_run`` 並查詢比較。

research 是上層編排層,不匯入 api 的 ``app`` 套件(避免 api↔engine/research
循環匯入,且不把 FastAPI/asyncpg 整包拉進 research)。改用 SQLAlchemy Core 對既有
``backtest_run`` 表做 app 級 INSERT / SELECT / DELETE —— 表結構由 api(schema 擁有者)
的手寫 alembic 維護(鐵律 2),這裡只是正常的應用程式讀寫(非手動 DDL/DML)。

連線只連 localhost(鐵律 4):URL 由 ``POSTGRES_*`` 環境變數組出,預設
``postgresql+psycopg2://postgres:1234@localhost:5432/jimq``。

``status`` 寫入大寫契約字面值 ``COMPLETED``(run 已跑完),VARCHAR 存(鐵律 11);
無外鍵(鐵律 12);金額 / 比率以 ``NUMERIC`` 存(鐵律 10)。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB

from jimq_core.schemas import BacktestRunSummary

_metadata = MetaData()

# Core 反射(以宣告對齊既有表,不發 DDL)。與 api 的 ORM model / 手寫 migration
# 欄位一致;research 端只讀寫,不負責建表。
backtest_run = Table(
    "backtest_run",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_name", String(128), nullable=False),
    Column("instrument_id", String(64), nullable=False),
    Column("bar_type", String(128), nullable=False),
    Column("timeframe", String(32), nullable=False),
    Column("start_time", DateTime(timezone=True), nullable=False),
    Column("end_time", DateTime(timezone=True), nullable=False),
    Column("run_group", String(64), nullable=True),
    Column("params", JSONB, nullable=False),
    Column("status", String(32), nullable=False),
    Column("total_return", Numeric(20, 8), nullable=True),
    Column("sharpe", Numeric(20, 8), nullable=True),
    Column("max_drawdown", Numeric(20, 8), nullable=True),
    Column("num_trades", BigInteger, nullable=True),
    Column("final_balance", Numeric(30, 8), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)

_COMPLETED = "COMPLETED"


def local_engine_url() -> str:
    """組出 localhost-only 同步 SQLAlchemy URL(psycopg2 驅動)。

    只連 localhost(鐵律 4);host 固定取 ``POSTGRES_HOST`` 但預設 localhost。
    """
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "1234")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "jimq")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def _row_values(summary: BacktestRunSummary, now: datetime) -> dict[str, Any]:
    return {
        "strategy_name": summary.strategy_name,
        "instrument_id": summary.instrument_id,
        "bar_type": summary.bar_type,
        "timeframe": summary.timeframe,
        "start_time": summary.start_time,
        "end_time": summary.end_time,
        "run_group": summary.run_group,
        "params": summary.params,
        "status": _COMPLETED,
        "total_return": summary.total_return,
        "sharpe": summary.sharpe,
        "max_drawdown": summary.max_drawdown,
        "num_trades": summary.num_trades,
        "final_balance": summary.final_balance,
        "created_at": now,
        "updated_at": now,
    }


def persist_summaries(
    summaries: list[BacktestRunSummary],
    *,
    engine_url: str | None = None,
) -> list[int]:
    """把每個 summary 以 app 級 INSERT 寫入 ``backtest_run``,回傳新增列 id 清單。"""
    if not summaries:
        return []
    engine = create_engine(engine_url or local_engine_url())
    now = datetime.now(UTC)
    ids: list[int] = []
    try:
        with engine.begin() as conn:
            for s in summaries:
                result = conn.execute(
                    insert(backtest_run)
                    .values(**_row_values(s, now))
                    .returning(backtest_run.c.id)
                )
                ids.append(int(result.scalar_one()))
    finally:
        engine.dispose()
    return ids


def query_runs(
    engine_url: str,
    *,
    run_group: str | None = None,
) -> list[dict[str, Any]]:
    """查回 run 結果(可選依 ``run_group`` 過濾)供比較;依 id 升冪。"""
    engine = create_engine(engine_url)
    try:
        stmt = select(backtest_run)
        if run_group is not None:
            stmt = stmt.where(backtest_run.c.run_group == run_group)
        stmt = stmt.order_by(backtest_run.c.id)
        with engine.connect() as conn:
            return [dict(row) for row in conn.execute(stmt).mappings().all()]
    finally:
        engine.dispose()


def delete_run_group(engine_url: str, run_group: str) -> int:
    """刪除某個 ``run_group`` 的所有列(測試清理 / 重跑用),回傳刪除筆數。"""
    engine = create_engine(engine_url)
    try:
        with engine.begin() as conn:
            result = conn.execute(
                delete(backtest_run).where(backtest_run.c.run_group == run_group)
            )
            return result.rowcount or 0
    finally:
        engine.dispose()
