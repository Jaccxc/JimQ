"""S0 foundation smoke tests (TDD tracer bullet for Phase 0).

These assert *behaviour* through public interfaces:
- the shared package `jimq_core` is importable and exposes placeholder modules
- the pinned `nautilus_trader` is installed and its version matches the contract
- the docker-compose Redis/Postgres services are healthy

Run: `uv run pytest tests/test_smoke.py`
The docker healthcheck test is opt-in via env (RUN_DOCKER_SMOKE=1) so the
import/version slice stays fast and offline.
"""

from __future__ import annotations

import os
import subprocess

import pytest

# Pinned NautilusTrader version (stable PyPI wheel, no Rust compile). See
# docs/design/20260616-1830-decisions-confirmed.md C3 + C4 (Python 3.12).
PINNED_NAUTILUS_VERSION = "1.228.0"


def test_jimq_core_importable():
    import jimq_core

    assert jimq_core.__version__


def test_jimq_core_placeholder_modules_importable():
    from jimq_core import constants, features, schemas

    # placeholders must at least carry their module identity
    assert constants.__name__ == "jimq_core.constants"
    assert features.__name__ == "jimq_core.features"
    assert schemas.__name__ == "jimq_core.schemas"


def test_jimq_core_redis_db_indices_are_distinct():
    """Nautilus message bus and boilerplate cache must use different Redis DB
    indices (contract rule 5 / repo-structure design point 4)."""
    from jimq_core import constants

    assert constants.REDIS_BUS_DB != constants.REDIS_CACHE_DB


def test_nautilus_trader_importable_and_pinned():
    import nautilus_trader

    assert nautilus_trader.__version__ == PINNED_NAUTILUS_VERSION


@pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_SMOKE") != "1",
    reason="set RUN_DOCKER_SMOKE=1 to run docker-compose healthcheck smoke test",
)
@pytest.mark.parametrize("service", ["redis", "postgres"])
def test_compose_service_healthy(service):
    """`docker compose up -d` must bring the service to a healthy state."""
    cid = subprocess.run(
        ["docker", "compose", "ps", "-q", service],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert cid, f"no container running for service {service!r}"

    health = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", cid],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert health == "healthy", f"{service} health = {health!r}"
