"""卡 #23 (W4) — research_job application model + FastCRUD 契約。

Behaviour through public interfaces:
- ResearchJobType / ResearchJobStatus app-level enums map to/from DB VARCHAR(32)
  via TypeDecorators(無 DB-native enum — 鐵律 11);
- the table carries no foreign keys(correlation_id 為純索引欄 — 鐵律 12);
- created_at 為 timestamptz(鐵律 10);
- FastCRUD round-trips a row against the real localhost Postgres with the
  Alembic-applied schema(opt-in RUN_DB_TESTS=1)。
"""

from __future__ import annotations

import os

import pytest


def test_job_type_and_status_enums_have_uppercase_literals():
    from app.models.research_job import ResearchJobStatus, ResearchJobType

    assert {t.value for t in ResearchJobType} == {"BUILD_DATASET", "TRAIN"}
    assert {s.value for s in ResearchJobStatus} == {
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
    }


def test_typedecorators_roundtrip_enum_and_varchar():
    from app.models.research_job import (
        ResearchJobStatus,
        ResearchJobStatusType,
        ResearchJobType,
        ResearchJobTypeType,
    )

    assert ResearchJobTypeType().process_bind_param(
        ResearchJobType.BUILD_DATASET, dialect=None
    ) == "BUILD_DATASET"
    assert (
        ResearchJobTypeType().process_result_value("TRAIN", dialect=None)
        is ResearchJobType.TRAIN
    )
    assert ResearchJobStatusType().process_bind_param(
        ResearchJobStatus.PENDING, dialect=None
    ) == "PENDING"


def test_research_job_table_has_no_foreign_keys():
    from app.models.research_job import ResearchJob

    assert len(ResearchJob.__table__.foreign_keys) == 0  # 鐵律 12


def test_research_job_created_at_is_timestamptz():
    from app.models.research_job import ResearchJob

    assert ResearchJob.__table__.c.created_at.type.timezone is True  # 鐵律 10


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)
@pytest.mark.anyio
async def test_crud_roundtrips_research_job():
    from app.core.db.database import async_engine, local_session
    from app.crud.crud_research_job import crud_research_jobs
    from app.models.research_job import ResearchJobStatus, ResearchJobType
    from app.schemas.research_job import ResearchJobCreate, ResearchJobRead

    await async_engine.dispose()

    async with local_session() as db:
        created = await crud_research_jobs.create(
            db=db,
            object=ResearchJobCreate(
                job_type=ResearchJobType.BUILD_DATASET,
                params={"symbol": "BTCUSDT-PERP.BINANCE", "timeframe": "1m"},
                correlation_id="corr-research-001",
            ),
            schema_to_select=ResearchJobRead,
            return_as_model=True,
        )
        job_id = created.id

        fetched = await crud_research_jobs.get(db=db, id=job_id)
        assert fetched is not None
        assert fetched["job_type"] == ResearchJobType.BUILD_DATASET
        assert fetched["status"] == ResearchJobStatus.PENDING  # model 預設
        assert fetched["params"] == {
            "symbol": "BTCUSDT-PERP.BINANCE",
            "timeframe": "1m",
        }
        assert fetched["correlation_id"] == "corr-research-001"
        assert fetched["created_at"].tzinfo is not None  # timestamptz

        await crud_research_jobs.db_delete(db=db, id=job_id)

    await async_engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
