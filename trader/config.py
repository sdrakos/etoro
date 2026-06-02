"""Config: load MASSIVE_KEY from etoro/back/.env (reuse — no duplication)."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
ETORO_ROOT = PACKAGE_ROOT.parent
BACK_ENV = ETORO_ROOT / "back" / ".env"

load_dotenv(BACK_ENV)

MASSIVE_KEY = (
    os.getenv("MASSIVE_KEY")
    or os.getenv("MASSIVE_API_KEY")
    or os.getenv("POLYGON_API_KEY")
)


def get_massive_key() -> str:
    """Return the Massive/Polygon key, raising only when it's actually needed."""
    if not MASSIVE_KEY:
        raise RuntimeError(f"MASSIVE_KEY missing from {BACK_ENV}")
    return MASSIVE_KEY


CACHE_DIR = Path(os.getenv("ETORO_CACHE_DIR", Path.home() / ".etoro"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "cache.db"
