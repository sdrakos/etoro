"""Aggregate eToro sub-routers into a single router mounted under /etoro."""
from fastapi import APIRouter

from routers.etoro import (
    settings,
    market_data,
    trading,
    social,
    agent_portfolios,
)

router = APIRouter()
router.include_router(settings.router)
router.include_router(market_data.router)
router.include_router(trading.router)
router.include_router(social.router)
router.include_router(agent_portfolios.router)
