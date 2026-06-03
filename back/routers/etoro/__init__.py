"""Aggregate eToro sub-routers into a single router mounted under /etoro."""
from fastapi import APIRouter

from routers.etoro import settings, proxy

router = APIRouter()
router.include_router(settings.router)
router.include_router(proxy.router)
