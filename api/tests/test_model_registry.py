"""P3-S4 — model_registry application model + FastCRUD (TDD slice 1).

Behaviour through public interfaces:
- ModelFramework app-level enum maps to/from the DB VARCHAR(32) via a
  TypeDecorator (no DB-native enum — 鐵律 11);
- the table carries no foreign keys; the training_run relation is a plain
  indexed column (鐵律 12);
- the FastCRUD instance round-trips a row against the real localhost Postgres
  with the Alembic-applied schema (timestamptz created_at, NUMERIC metrics +
  heterogeneous JSONB metrics — 鐵律 2/10/12).

The DB round-trip is opt-in (RUN_DB_TESTS=1) so the offline unit slice stays
fast; CI/local with infra up runs the full slice.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest


def test_framework_enum_has_uppercase_contract_literals():
    from app.models.model_registry import ModelFramework

    assert {f.value for f in ModelFramework} == {
        "TORCH",
        "SKLEARN",
        "STABLE_BASELINES3",
    }


def test_framework_typedecorator_roundtrips_enum_and_varchar():
    """TypeDecorator stores the uppercase literal and rehydrates the enum."""
    from app.models.model_registry import ModelFramework, ModelFrameworkType

    td = ModelFrameworkType()
    bound = td.process_bind_param(ModelFramework.TORCH, dialect=None)
    assert bound == "TORCH"  # stored as plain VARCHAR

    result = td.process_result_value("SKLEARN", dialect=None)
    assert result is ModelFramework.SKLEARN


def test_model_registry_table_has_no_foreign_keys():
    from app.models.model_registry import ModelRegistry

    assert len(ModelRegistry.__table__.foreign_keys) == 0  # 鐵律 12


def test_model_registry_created_at_is_timestamptz():
    from app.models.model_registry import ModelRegistry

    created_at = ModelRegistry.__table__.c.created_at
    assert created_at.type.timezone is True  # timestamptz (鐵律 10)


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres round-trip",
)
@pytest.mark.anyio
async def test_crud_roundtrips_model_registry():
    from app.core.db.database import async_engine, local_session
    from app.crud.crud_model_registry import crud_model_registry
    from app.models.model_registry import ModelFramework
    from app.schemas.model_registry import ModelRegistryCreate, ModelRegistryRead

    async with local_session() as db:
        created = await crud_model_registry.create(
            db=db,
            object=ModelRegistryCreate(
                name="ppo_btc_perp",
                version="v1",
                artifact_path="data/models/ppo_btc_perp/v1",
                framework=ModelFramework.STABLE_BASELINES3,
                sharpe=Decimal("1.42"),
                metrics={"custom_kl": 0.013, "explained_var": 0.88},
                training_run_id="grid-abc-007",
            ),
            schema_to_select=ModelRegistryRead,
            return_as_model=True,
        )
        model_id = created.id

        fetched = await crud_model_registry.get(db=db, id=model_id)
        assert fetched is not None
        assert fetched["name"] == "ppo_btc_perp"
        assert fetched["version"] == "v1"
        assert fetched["artifact_path"] == "data/models/ppo_btc_perp/v1"
        assert fetched["framework"] == ModelFramework.STABLE_BASELINES3
        assert fetched["training_run_id"] == "grid-abc-007"
        # heterogeneous model metrics live in JSONB (鐵律 10)
        assert fetched["metrics"] == {"custom_kl": 0.013, "explained_var": 0.88}
        # key metric is a first-class NUMERIC column
        assert Decimal(str(fetched["sharpe"])) == Decimal("1.42")
        assert fetched["created_at"].tzinfo is not None  # timestamptz

        await crud_model_registry.db_delete(db=db, id=model_id)

    await async_engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
