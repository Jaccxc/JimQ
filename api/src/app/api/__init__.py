from fastapi import APIRouter

from .v1 import router as v1_router
from .v1.health import router as health_router

# /health lives at the root for liveness probes; resource routers under /api/v1.
router = APIRouter()
router.include_router(health_router)

api_router = APIRouter(prefix="/api")
api_router.include_router(v1_router)
router.include_router(api_router)
