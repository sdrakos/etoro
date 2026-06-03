"""Lazy supabase-py client (service_role) for QUANTIQ backend."""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


@lru_cache(maxsize=1)
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing from back/.env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
