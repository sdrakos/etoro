"""Generic passthrough to the eToro API — forwards any /etoro/api/{v1,v2}/<path>.

Keeps QUANTIQ in lockstep with the upstream API. Real-money execution paths are
gated by the same guard used elsewhere.
"""
import json as _json
import os
from fastapi import APIRouter, Depends, HTTPException, Request

from etoro_api.client import EtoroClient
from etoro_api.deps import get_etoro_client

router = APIRouter(tags=["etoro:proxy"])

_ALLOWED_VERSIONS = {"v1", "v2"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def is_real_execution(method: str, full_path: str) -> bool:
    return (method.upper() in _WRITE_METHODS
            and "/trading/execution/" in full_path
            and "/demo/" not in full_path)


def guard_real() -> None:
    if os.getenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false").lower() not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=403,
            detail="real-money execution disabled. Set QUANTIQ_ALLOW_REAL_EXECUTION=true to enable.")


@router.api_route("/etoro/api/{version}/{path:path}",
                  methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(version: str, path: str, request: Request,
                client: EtoroClient = Depends(get_etoro_client)):
    if version not in _ALLOWED_VERSIONS:
        raise HTTPException(status_code=404, detail=f"unknown API version: {version!r}")
    full = f"/api/{version}/{path}"
    if is_real_execution(request.method, full):
        guard_real()
    params = dict(request.query_params) or None
    body = None
    if request.method in _WRITE_METHODS:
        raw = await request.body()
        if raw:
            try:
                body = _json.loads(raw)
            except Exception:
                body = None
    return client.request(request.method, full, params=params, json=body)
