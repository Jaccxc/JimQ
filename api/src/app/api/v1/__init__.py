from fastapi import APIRouter

from .backtests import router as backtests_router

router = APIRouter(prefix="/v1")
router.include_router(backtests_router)
