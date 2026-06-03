"""Server-side eToro client for shared market-data (no tenant).

Uses the app's own ETORO_* keys from back/.env. For public/market-data routes
(e.g. the screener) that must not require a per-user X-User-Id header.
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import HTTPException
from dotenv import load_dotenv

from etoro_api.client import EtoroClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_server_client() -> EtoroClient:
    pub = os.getenv("ETORO_PUBLIC_KEY")
    usr = os.getenv("ETORO_PRIVATE_KEY")
    if not pub or not usr:
        raise HTTPException(status_code=503, detail="eToro server keys missing from back/.env")
    return EtoroClient(pub, usr, environment="demo")
