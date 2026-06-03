"""Per-tenant eToro key vault: Fernet-encrypted values stored in Supabase."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv

from supabase_client import get_supabase

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TABLE = "etoro_credentials"


@dataclass
class Credentials:
    public_key: str
    user_key: str
    environment: str


def _fernet() -> Fernet:
    key = os.getenv("QUANTIQ_ENC_KEY")
    if not key:
        raise RuntimeError("QUANTIQ_ENC_KEY missing from back/.env")
    return Fernet(key.encode() if isinstance(key, str) else key)


def set_credentials(user_id: str, public_key: str, user_key: str,
                    environment: str = "demo") -> None:
    f = _fernet()
    get_supabase().table(TABLE).upsert({
        "user_id": user_id,
        "public_key_enc": f.encrypt(public_key.encode()).decode(),
        "user_key_enc": f.encrypt(user_key.encode()).decode(),
        "environment": environment,
    }).execute()


def get_credentials(user_id: str) -> Credentials | None:
    res = get_supabase().table(TABLE).select("*").eq("user_id", user_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        return None
    f = _fernet()
    r = rows[0]
    return Credentials(
        public_key=f.decrypt(r["public_key_enc"].encode()).decode(),
        user_key=f.decrypt(r["user_key_enc"].encode()).decode(),
        environment=r.get("environment", "demo"),
    )


def has_credentials(user_id: str) -> bool:
    res = get_supabase().table(TABLE).select("user_id").eq("user_id", user_id).limit(1).execute()
    return bool(res.data)


def delete_credentials(user_id: str) -> None:
    get_supabase().table(TABLE).delete().eq("user_id", user_id).execute()
