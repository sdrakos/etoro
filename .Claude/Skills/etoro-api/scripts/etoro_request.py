#!/usr/bin/env python3
"""Authenticated eToro Public API request helper.

Keys are read from the repo's single source of truth, etoro/back/.env:
  ETORO_PUBLIC_KEY   -> x-api-key
  ETORO_PRIVATE_KEY  -> x-user-key
A fresh x-request-id (UUID) is generated per call. Stdlib only — no deps.

Examples:
  python etoro_request.py GET /market-data/search \
    "internalSymbolFull=BTC&fields=instrumentId,internalSymbolFull,displayname"

  python etoro_request.py GET /watchlists

  python etoro_request.py POST /trading/execution/demo/market-open-orders/by-amount \
    --json '{"InstrumentID":100000,"IsBuy":true,"Leverage":1,"Amount":100}'
"""
from __future__ import annotations
import argparse
import json
import sys
import uuid
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://public-api.etoro.com/api/v1"


def _find_env() -> Path:
    """Search upward from this script for etoro/back/.env (install-path agnostic)."""
    d = Path(__file__).resolve().parent
    for _ in range(8):
        d = d.parent
        cand = d / "back" / ".env"
        if cand.exists():
            return cand
    sys.exit("etoro_request: could not locate back/.env (searched 8 levels up).")


def _load_keys() -> tuple[str, str]:
    env_path = _find_env()
    pub = priv = None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key == "ETORO_PUBLIC_KEY":
            pub = val
        elif key == "ETORO_PRIVATE_KEY":
            priv = val
    if not pub or not priv:
        sys.exit(f"etoro_request: ETORO_PUBLIC_KEY / ETORO_PRIVATE_KEY missing from {env_path}")
    return pub, priv


def request(method: str, path: str, query: str | None = None,
            body: object | None = None) -> tuple[int, str]:
    pub, priv = _load_keys()
    url = BASE_URL + path
    if query:
        url += ("&" if "?" in url else "?") + query
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "x-request-id": str(uuid.uuid4()),
        "x-api-key": pub,
        "x-user-key": priv,
        # eToro sits behind Cloudflare, which 403s the default Python-urllib UA.
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) etoro-api-skill/1.0",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="eToro Public API request helper")
    p.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    p.add_argument("path", help="path relative to /api/v1, e.g. /watchlists")
    p.add_argument("query", nargs="?", default=None,
                   help="raw query string, e.g. 'fields=instrumentId&searchText=BTC'")
    p.add_argument("--json", dest="body", default=None, help="JSON request body")
    args = p.parse_args(argv)

    body = json.loads(args.body) if args.body else None
    status, text = request(args.method, args.path, args.query, body)
    print(f"HTTP {status}")
    try:
        print(json.dumps(json.loads(text), indent=2, ensure_ascii=False))
    except Exception:
        print(text)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
