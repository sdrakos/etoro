from dataclasses import asdict, is_dataclass
from itertools import islice
from typing import Any, Iterable

from fastapi import HTTPException


def to_dict(obj: Any) -> Any:
    """Convert SDK return objects (dataclass / namespace / primitive) to JSON-safe."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_dict(x) for x in obj]
    if is_dataclass(obj):
        return {k: to_dict(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "__dict__"):
        return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)


def take(iterator: Iterable, limit: int | None) -> list:
    """Consume an iterator with optional cap (auto-pagination from the SDK)."""
    if limit is None:
        return [to_dict(x) for x in iterator]
    return [to_dict(x) for x in islice(iterator, limit)]


def safe_call(fn, *args, **kwargs):
    """Wrap SDK calls; surface API errors as HTTP 4xx/5xx."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = str(e)
        code = 502
        if "401" in msg or "unauthorized" in msg.lower():
            code = 401
        elif "404" in msg or "not found" in msg.lower():
            code = 404
        elif "429" in msg or "rate" in msg.lower():
            code = 429
        raise HTTPException(status_code=code, detail=msg)
