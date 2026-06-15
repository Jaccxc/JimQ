from fastapi import APIRouter

from .backtests import router as backtests_router
from .bars import router as bars_router

router = APIRouter(prefix="/v1")
router.include_router(backtests_router)
router.include_router(bars_router)
