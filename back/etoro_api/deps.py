"""FastAPI dependency that resolves the tenant's eToro client.

Dev mode: tenant identified by the `X-User-Id` header; keys read from the vault
(service_role), falling back to back/.env ETORO_* keys. Replace this dependency
with Supabase JWT verification when real multitenant auth lands — nothing else
in the stack changes.
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import Header, HTTPException
from dotenv import load_dotenv

from etoro_api import vault
from etoro_api.client import EtoroClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_etoro_client(x_user_id: str = Header(..., alias="X-User-Id")) -> EtoroClient:
    creds = vault.get_credentials(x_user_id)
    if creds:
        return EtoroClient(creds.public_key, creds.user_key, environment=creds.environment)
    pub = os.getenv("ETORO_PUBLIC_KEY")
    usr = os.getenv("ETORO_PRIVATE_KEY")
    if pub and usr:
        return EtoroClient(pub, usr, environment="demo")
    raise HTTPException(status_code=400, detail=f"no eToro credentials for user {x_user_id}")
