"""P3-S4 — model artifact store + register/retrieve roundtrip (TDD slice 2).

Behaviour through public interfaces:
- ``save_artifact`` copies a model file into
  ``<models_root>/<name>/<version>/`` (gitignored data/models) and returns the
  destination directory;
- ``load_artifact`` returns that directory back for a (name, version);
- ``register`` saves the artifact AND writes the metadata row, and
  ``retrieve`` round-trips both metadata and the on-disk artifact path.

The register/retrieve roundtrip hits the real localhost Postgres and is opt-in
(RUN_DB_TESTS=1); the pure-filesystem save/load slice always runs.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest


def test_save_artifact_copies_file_into_name_version_dir(tmp_path):
    from app.services.model_store import ModelStore

    src = tmp_path / "weights.pt"
    src.write_bytes(b"fake-torch-weights")

    store = ModelStore(models_root=tmp_path / "models")
    dest_dir = store.save_artifact(name="ppo_btc_perp", version="v1", source=src)

    # stored under <root>/<name>/<version>/
    assert dest_dir == tmp_path / "models" / "ppo_btc_perp" / "v1"
    assert (dest_dir / "weights.pt").read_bytes() == b"fake-torch-weights"


def test_load_artifact_returns_saved_dir(tmp_path):
    from app.services.model_store import ModelStore

    src = tmp_path / "model.pkl"
    src.write_bytes(b"sklearn-pickle")

    store = ModelStore(models_root=tmp_path / "models")
    store.save_artifact(name="rf_btc", version="v2", source=src)

    loaded = store.load_artifact(name="rf_btc", version="v2")
    assert loaded == tmp_path / "models" / "rf_btc" / "v2"
    assert (loaded / "model.pkl").read_bytes() == b"sklearn-pickle"


def test_load_artifact_missing_raises(tmp_path):
    from app.services.model_store import ModelStore

    store = ModelStore(models_root=tmp_path / "models")
    with pytest.raises(FileNotFoundError):
        store.load_artifact(name="nope", version="v0")


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 to run the localhost Postgres register/retrieve roundtrip",
)
@pytest.mark.anyio
async def test_register_then_retrieve_roundtrip(tmp_path):
    from app.core.db.database import async_engine, local_session
    from app.models.model_registry import ModelFramework
    from app.services.model_store import ModelStore

    src = tmp_path / "policy.zip"
    src.write_bytes(b"sb3-policy-archive")

    store = ModelStore(models_root=tmp_path / "models")

    async with local_session() as db:
        record = await store.register(
            db=db,
            name="ppo_roundtrip",
            version="v1",
            framework=ModelFramework.STABLE_BASELINES3,
            source=src,
            sharpe=Decimal("1.71"),
            metrics={"explained_var": 0.91, "n_updates": 1200},
            training_run_id="grid-xyz-001",
        )
        model_id = record.id
        # artifact was saved to disk during register
        assert (tmp_path / "models" / "ppo_roundtrip" / "v1" / "policy.zip").exists()

        meta, artifact_dir = await store.retrieve(db=db, name="ppo_roundtrip", version="v1")
        assert meta.id == model_id
        assert meta.framework == ModelFramework.STABLE_BASELINES3
        assert meta.training_run_id == "grid-xyz-001"
        assert meta.metrics == {"explained_var": 0.91, "n_updates": 1200}
        assert Decimal(str(meta.sharpe)) == Decimal("1.71")
        # retrieve hands back the on-disk artifact dir with the weights present
        assert artifact_dir == tmp_path / "models" / "ppo_roundtrip" / "v1"
        assert (artifact_dir / "policy.zip").read_bytes() == b"sb3-policy-archive"

        # the metadata row matches what register persisted (artifact_path stored)
        assert meta.artifact_path == str(artifact_dir)

        from app.crud.crud_model_registry import crud_model_registry

        await crud_model_registry.db_delete(db=db, id=model_id)

    await async_engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
