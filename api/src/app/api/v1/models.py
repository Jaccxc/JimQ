"""models resource router (FastCRUD auto-endpoints, no auth — auth stripped).

GET /api/v1/models lists registered models (沿用既有 v1 / FastCRUD 風格, 卡 #17).
"""

from fastcrud import crud_router

from ...core.db.database import async_get_db
from ...crud.crud_model_registry import crud_model_registry
from ...models.model_registry import ModelRegistry
from ...schemas.model_registry import (
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
)

router = crud_router(
    session=async_get_db,
    model=ModelRegistry,
    crud=crud_model_registry,
    create_schema=ModelRegistryCreate,
    update_schema=ModelRegistryUpdate,
    select_schema=ModelRegistryRead,
    path="/models",
    tags=["models"],
)
