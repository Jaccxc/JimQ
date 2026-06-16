from fastapi import APIRouter

from .backtests import router as backtests_router
from .bars import router as bars_router
from .mlflow import router as mlflow_router
from .models import router as models_router
from .research import router as research_router
from .strategies import router as strategies_router

router = APIRouter(prefix="/v1")
router.include_router(backtests_router)
router.include_router(bars_router)
router.include_router(mlflow_router)
router.include_router(models_router)
router.include_router(research_router)
router.include_router(strategies_router)
