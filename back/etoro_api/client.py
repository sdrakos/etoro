"""Thin authenticated HTTP client for the eToro Public API."""
from __future__ import annotations
import uuid
from typing import Any, Optional
import httpx
from fastapi import HTTPException

BASE_URL = "https://public-api.etoro.com/api/v1"
# eToro is behind Cloudflare, which 403s the default httpx/urllib UA (error 1010).
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QUANTIQ/1.0"


def drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


class EtoroClient:
    def __init__(self, public_key: str, user_key: str, *,
                 environment: str = "demo", timeout: float = 30.0):
        self.public_key = public_key
        self.user_key = user_key
        self.environment = environment
        self._timeout = timeout

    def _headers(self) -> dict:
        return {
            "x-request-id": str(uuid.uuid4()),
            "x-api-key": self.public_key,
            "x-user-key": self.user_key,
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, *,
                params: Optional[dict] = None, json: Any = None) -> Any:
        url = BASE_URL + path
        try:
            with httpx.Client(timeout=self._timeout) as c:
                resp = c.request(method, url, params=params, json=json,
                                 headers=self._headers())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"eToro request failed: {e}")
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        if not resp.content:
            return {"status": resp.status_code}
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code, "raw": resp.text}
