"""卡 #18 — research 端 model_registry glue round-trip(localhost Postgres)。

驗證 research 用 SQLAlchemy Core(app 級讀寫,非 DDL/DML)把模型 metadata 登錄到
api 擁有的 ``model_registry`` 表並查得回。需 localhost Postgres(鐵律 4);DB 不可
用時自動 skip(離線環境)。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from jimq_research.training.model_registry import get_model, register_model
from jimq_research.training.store import local_engine_url


def _db_available(url: str) -> bool:
    try:
        eng = create_engine(url)
        with eng.connect() as conn:
            conn.execute(text("select 1"))
        eng.dispose()
        return True
    except Exception:
        return False


@pytest.fixture()
def engine_url():
    url = local_engine_url()
    if not _db_available(url):
        pytest.skip("localhost Postgres 不可用,跳過 registry round-trip")
    return url


def test_register_and_get_roundtrip(engine_url):
    name = "test-stub"
    version = f"v-{uuid.uuid4().hex[:8]}"
    artifact_path = f"/tmp/data/models/{name}/{version}"

    new_id = register_model(
        name=name,
        version=version,
        artifact_path=artifact_path,
        framework="SKLEARN",
        sharpe=1.23,
        metrics={"stub": True, "n_features": 2},
        engine_url=engine_url,
    )
    assert isinstance(new_id, int)

    row = get_model(name=name, version=version, engine_url=engine_url)
    assert row is not None
    assert row["name"] == name
    assert row["version"] == version
    assert row["artifact_path"] == artifact_path
    assert row["framework"] == "SKLEARN"
    assert row["metrics"] == {"stub": True, "n_features": 2}

    # 清理(app 級 DELETE)。
    eng = create_engine(engine_url)
    with eng.begin() as conn:
        conn.execute(
            text("delete from model_registry where id = :id"), {"id": new_id}
        )
    eng.dispose()
