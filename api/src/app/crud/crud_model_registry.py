"""FastCRUD instance for ``model_registry`` (sticks to the boilerplate pattern)."""

from fastcrud import FastCRUD

from ..models.model_registry import ModelRegistry
from ..schemas.model_registry import (
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
)

CRUDModelRegistry = FastCRUD[
    ModelRegistry,
    ModelRegistryCreate,
    ModelRegistryUpdate,
    ModelRegistryUpdate,
    ModelRegistryRead,
    ModelRegistryRead,
]
crud_model_registry = CRUDModelRegistry(ModelRegistry)
