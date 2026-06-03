"""Per-tenant eToro credential management (writes to the vault, no eToro call)."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from etoro_api import vault

router = APIRouter(prefix="/etoro/credentials", tags=["etoro:settings"])


class CredentialsIn(BaseModel):
    public_key: str
    user_key: str
    environment: str = "demo"


@router.post("")
def set_credentials(body: CredentialsIn, x_user_id: str = Header(..., alias="X-User-Id")):
    if body.environment not in ("real", "demo"):
        raise HTTPException(status_code=422, detail="environment must be 'real' or 'demo'")
    vault.set_credentials(x_user_id, body.public_key, body.user_key, body.environment)
    return {"status": "ok", "environment": body.environment}


@router.get("")
def get_status(x_user_id: str = Header(..., alias="X-User-Id")):
    creds = vault.get_credentials(x_user_id)
    if not creds:
        return {"has_keys": False}
    return {"has_keys": True, "environment": creds.environment,
            "public_key_last4": creds.public_key[-4:]}


@router.delete("")
def delete_credentials(x_user_id: str = Header(..., alias="X-User-Id")):
    vault.delete_credentials(x_user_id)
    return {"status": "deleted"}
