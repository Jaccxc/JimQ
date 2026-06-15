"""Model artifact store + registry glue (卡 #17 / decisions-confirmed C10).

``ModelStore`` owns the on-disk layout of registered model weights under
``data/models/<name>/<version>/`` (gitignored) and ties it to the
``model_registry`` metadata table:

- :meth:`save_artifact` / :meth:`load_artifact` are the pure-filesystem half
  (no DB) — research training code can save weights via the same convention;
- :meth:`register` saves the artifact AND writes the metadata row;
- :meth:`retrieve` returns the metadata row together with the on-disk artifact
  directory.

Schema ownership stays in api (鐵律: registry DB/表/API live here); research
calls ``register`` after training.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..crud.crud_model_registry import crud_model_registry
from ..models.model_registry import ModelFramework
from ..schemas.model_registry import ModelRegistryCreate, ModelRegistryRead


@dataclass
class ModelStore:
    """Filesystem-backed artifact store keyed by ``(name, version)``."""

    models_root: Path = Path(settings.MODELS_ROOT)

    def __post_init__(self) -> None:
        self.models_root = Path(self.models_root)

    def artifact_dir(self, name: str, version: str) -> Path:
        """Destination directory for a model's artifacts (not created here)."""
        return self.models_root / name / version

    def save_artifact(self, name: str, version: str, source: str | Path) -> Path:
        """Copy ``source`` into ``<root>/<name>/<version>/`` and return the dir."""
        source = Path(source)
        dest_dir = self.artifact_dir(name, version)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest_dir / source.name)
        return dest_dir

    def load_artifact(self, name: str, version: str) -> Path:
        """Return the artifact directory for ``(name, version)``.

        Raises ``FileNotFoundError`` if nothing was ever saved there.
        """
        dest_dir = self.artifact_dir(name, version)
        if not dest_dir.is_dir():
            raise FileNotFoundError(
                f"no artifact for name={name!r} version={version!r} under {self.models_root}"
            )
        return dest_dir

    async def register(
        self,
        *,
        db: AsyncSession,
        name: str,
        version: str,
        framework: ModelFramework,
        source: str | Path,
        sharpe: Decimal | None = None,
        metrics: dict[str, Any] | None = None,
        training_run_id: str | None = None,
    ) -> ModelRegistryRead:
        """Save the artifact then persist the metadata row; returns the row."""
        dest_dir = self.save_artifact(name=name, version=version, source=source)
        return await crud_model_registry.create(
            db=db,
            object=ModelRegistryCreate(
                name=name,
                version=version,
                artifact_path=str(dest_dir),
                framework=framework,
                sharpe=sharpe,
                metrics=metrics or {},
                training_run_id=training_run_id,
            ),
            schema_to_select=ModelRegistryRead,
            return_as_model=True,
        )

    async def retrieve(
        self, *, db: AsyncSession, name: str, version: str
    ) -> tuple[ModelRegistryRead, Path]:
        """Return ``(metadata, artifact_dir)`` for ``(name, version)``.

        Raises ``LookupError`` if no metadata row exists, ``FileNotFoundError``
        if the row exists but its on-disk artifact is missing.
        """
        row = await crud_model_registry.get(
            db=db,
            name=name,
            version=version,
            schema_to_select=ModelRegistryRead,
            return_as_model=True,
        )
        if row is None:
            raise LookupError(f"no registered model name={name!r} version={version!r}")
        artifact_dir = self.load_artifact(name=name, version=version)
        return row, artifact_dir
