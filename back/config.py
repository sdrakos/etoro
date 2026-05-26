import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MASSIVE_KEY = os.getenv("MASSIVE_KEY") or os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
if not MASSIVE_KEY:
    raise RuntimeError("MASSIVE_KEY missing from back/.env")

try:
    from massive import RESTClient  # post-rebrand
except ImportError:
    from polygon import RESTClient  # pre-rebrand (same API surface)


@lru_cache(maxsize=1)
def get_client() -> RESTClient:
    return RESTClient(api_key=MASSIVE_KEY)
