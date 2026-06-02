# QUANTIQ — Supabase foundation + eToro router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a local Supabase backend with an encrypted per-tenant eToro key vault, and a FastAPI router exposing every eToro Public API endpoint, with keys read from the vault.

**Architecture:** Local Supabase (CLI) holds an `etoro_credentials` table (RLS, app-level Fernet-encrypted values). FastAPI `back/` gains an `etoro_api/` package (httpx client, vault, tenant dependency) and a `routers/etoro/` package (5 sub-routers mounted under `/etoro`). The tenant is identified by a dev `X-User-Id` header now (swapped for Supabase JWT later); `service_role` reads the vault.

**Tech Stack:** Python 3.11+, FastAPI, httpx, supabase-py, cryptography (Fernet), Supabase CLI (local stack), pytest.

All commands assume cwd is `etoro/back/` unless stated. Tests are offline (supabase-py + httpx mocked). Clean commit messages, **no** Co-Authored-By trailer.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/requirements.txt` | add `supabase`, `cryptography`, `httpx` (pinned) |
| `back/.env` / `back/.env.example` | add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `QUANTIQ_ENC_KEY` |
| `supabase/` (CLI) + `supabase/migrations/<ts>_etoro_credentials.sql` | local stack + schema/RLS |
| `back/supabase_client.py` | lazy supabase-py client (service_role) |
| `back/etoro_api/__init__.py` | package marker |
| `back/etoro_api/client.py` | `EtoroClient` httpx wrapper + `drop_none` |
| `back/etoro_api/vault.py` | Fernet encrypt + supabase upsert/read of credentials |
| `back/etoro_api/deps.py` | `get_etoro_client` FastAPI dependency (+ dev `.env` fallback) |
| `back/routers/etoro/__init__.py` | aggregate sub-routers into one `router` |
| `back/routers/etoro/settings.py` | `/etoro/credentials` (vault writes) |
| `back/routers/etoro/market_data.py` | `/etoro/market-data/*` |
| `back/routers/etoro/trading.py` | `/etoro/trading/*` (+ real-execution guard) |
| `back/routers/etoro/social.py` | feeds, watchlists, curated, recommendations, copiers, user-info |
| `back/routers/etoro/agent_portfolios.py` | `/etoro/sub-portfolios/*` |
| `back/main.py` | include the aggregated eToro router |
| `back/tests/test_*.py` | offline tests per module |

> Naming note: the integration package is `etoro_api/` (not `etoro/`) to avoid confusion with `routers/etoro/`.

---

### Task 1: Dependencies, env, and local Supabase + migration

**Files:**
- Modify: `back/requirements.txt`, `back/.env`, `back/.env.example`
- Create: `supabase/` (via CLI), `supabase/migrations/<ts>_etoro_credentials.sql`

- [ ] **Step 1: Add dependencies**

Append to `back/requirements.txt`:

```
supabase>=2.8,<3
cryptography>=42
httpx>=0.27
```

- [ ] **Step 2: Install deps**

Run: `python -m pip install -r requirements.txt`
Expected: installs supabase, cryptography, httpx with no error.

- [ ] **Step 3: Initialize and start local Supabase**

> **CLI note:** the standalone `supabase` CLI is NOT installed on this machine, but `npx` (Node.js) IS. Prefix every Supabase CLI command with `npx` — e.g. `npx supabase start`. (First run downloads the CLI.) Docker Desktop is installed and the daemon is running, so the local stack will come up.

Run (from `etoro/`):
```bash
npx supabase init
npx supabase start
```
Expected: `npx supabase start` prints `API URL: http://127.0.0.1:54321`, `DB URL`, `service_role key`, `anon key`.

- [ ] **Step 4: Generate a Fernet key**

Run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
Copy the output for the next step.

- [ ] **Step 5: Add env values to `back/.env`**

Append to `back/.env` (use the real values printed by `supabase start` and the key from Step 4):

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=<service_role key from supabase start>
QUANTIQ_ENC_KEY=<Fernet key from step 4>
QUANTIQ_ALLOW_REAL_EXECUTION=false
```

Append matching placeholders to `back/.env.example`:

```
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=
QUANTIQ_ENC_KEY=
QUANTIQ_ALLOW_REAL_EXECUTION=false
```

- [ ] **Step 6: Create the migration file**

Run (from `etoro/`): `npx supabase migration new etoro_credentials`
This creates `supabase/migrations/<timestamp>_etoro_credentials.sql`. Put this SQL in it:

```sql
create table if not exists public.etoro_credentials (
    user_id        uuid primary key,
    public_key_enc text not null,
    user_key_enc   text not null,
    environment    text not null default 'demo' check (environment in ('real','demo')),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

alter table public.etoro_credentials enable row level security;

create policy "own creds - select" on public.etoro_credentials
    for select to authenticated using ((select auth.uid()) = user_id);
create policy "own creds - insert" on public.etoro_credentials
    for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own creds - update" on public.etoro_credentials
    for update to authenticated using ((select auth.uid()) = user_id)
                                    with check ((select auth.uid()) = user_id);
create policy "own creds - delete" on public.etoro_credentials
    for delete to authenticated using ((select auth.uid()) = user_id);
```

- [ ] **Step 7: Apply the migration locally**

Run (from `etoro/`): `npx supabase migration up`
Expected: applies without error. Verify: `npx supabase migration list --local` shows the migration as applied.

- [ ] **Step 8: Commit**

```bash
git add back/requirements.txt back/.env.example supabase/config.toml supabase/migrations/
git commit -m "feat(quantiq): local supabase + etoro_credentials migration + deps"
```

> `back/.env` is gitignored — do not commit it.

---

### Task 2: Supabase client module

**Files:**
- Create: `back/supabase_client.py`
- Test: `back/tests/test_supabase_client.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_supabase_client.py
import importlib
import pytest


def test_get_supabase_raises_without_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    import supabase_client
    importlib.reload(supabase_client)
    supabase_client.get_supabase.cache_clear()
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        supabase_client.get_supabase()


def test_get_supabase_builds_client(monkeypatch):
    import supabase_client
    importlib.reload(supabase_client)
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setattr(supabase_client, "SUPABASE_SERVICE_ROLE_KEY", "svc")
    supabase_client.get_supabase.cache_clear()
    captured = {}
    monkeypatch.setattr(supabase_client, "create_client",
                        lambda url, key: captured.update(url=url, key=key) or "CLIENT")
    assert supabase_client.get_supabase() == "CLIENT"
    assert captured == {"url": "http://localhost:54321", "key": "svc"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_supabase_client.py -v`
Expected: FAIL — `No module named 'supabase_client'`.

- [ ] **Step 3: Write `back/supabase_client.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_supabase_client.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add supabase_client.py tests/test_supabase_client.py
git commit -m "feat(quantiq): lazy supabase-py service_role client"
```

---

### Task 3: Key vault (Fernet + supabase)

**Files:**
- Create: `back/etoro_api/__init__.py`, `back/etoro_api/vault.py`
- Test: `back/tests/test_etoro_vault.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_vault.py
from unittest.mock import MagicMock
import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def fake_supabase():
    """A MagicMock standing in for supabase-py's fluent table() API."""
    sb = MagicMock()
    table = sb.table.return_value
    table.upsert.return_value.execute.return_value = MagicMock(data=[{}])
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    return sb


@pytest.fixture
def vault(monkeypatch, fake_supabase):
    monkeypatch.setenv("QUANTIQ_ENC_KEY", Fernet.generate_key().decode())
    import etoro_api.vault as vault
    monkeypatch.setattr(vault, "get_supabase", lambda: fake_supabase)
    return vault


def test_set_credentials_stores_ciphertext_not_plaintext(vault, fake_supabase):
    vault.set_credentials("11111111-1111-1111-1111-111111111111",
                          "PUBKEY", "USERKEY", "demo")
    row = fake_supabase.table.return_value.upsert.call_args.args[0]
    assert row["user_id"] == "11111111-1111-1111-1111-111111111111"
    assert row["environment"] == "demo"
    # values are encrypted — plaintext must not appear
    assert "PUBKEY" not in row["public_key_enc"]
    assert "USERKEY" not in row["user_key_enc"]


def test_get_credentials_roundtrip(vault, fake_supabase):
    f = vault._fernet()
    fake_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{
            "user_id": "u", "environment": "demo",
            "public_key_enc": f.encrypt(b"PUBKEY").decode(),
            "user_key_enc": f.encrypt(b"USERKEY").decode(),
        }]
    )
    creds = vault.get_credentials("u")
    assert creds is not None
    assert creds.public_key == "PUBKEY"
    assert creds.user_key == "USERKEY"
    assert creds.environment == "demo"


def test_get_credentials_missing_returns_none(vault):
    assert vault.get_credentials("nobody") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_vault.py -v`
Expected: FAIL — `No module named 'etoro_api'`.

- [ ] **Step 3: Create the package + `vault.py`**

`back/etoro_api/__init__.py`:
```python
"""eToro integration: HTTP client, key vault, FastAPI tenant dependency."""
```

`back/etoro_api/vault.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_vault.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add etoro_api/__init__.py etoro_api/vault.py tests/test_etoro_vault.py
git commit -m "feat(quantiq): fernet-encrypted etoro key vault"
```

---

### Task 4: eToro HTTP client

**Files:**
- Create: `back/etoro_api/client.py`
- Test: `back/tests/test_etoro_client.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_client.py
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException


def _resp(status=200, json_body=None, text="", content=b"x"):
    r = MagicMock()
    r.status_code = status
    r.content = content
    r.text = text
    if json_body is None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_body
    return r


def test_request_sends_auth_and_cloudflare_headers():
    from etoro_api.client import EtoroClient
    client = EtoroClient("PUB", "USR", environment="demo")
    with patch("etoro_api.client.httpx.Client") as Cli:
        ctx = Cli.return_value.__enter__.return_value
        ctx.request.return_value = _resp(200, {"ok": True})
        out = client.request("GET", "/watchlists", params={"a": 1})
    assert out == {"ok": True}
    _, kwargs = ctx.request.call_args
    h = kwargs["headers"]
    assert h["x-api-key"] == "PUB"
    assert h["x-user-key"] == "USR"
    assert h["User-Agent"].startswith("Mozilla/")  # Cloudflare needs a browser UA
    assert len(h["x-request-id"]) >= 8  # a UUID
    assert kwargs["params"] == {"a": 1}


def test_request_raises_httpexception_on_error_status():
    from etoro_api.client import EtoroClient
    client = EtoroClient("PUB", "USR")
    with patch("etoro_api.client.httpx.Client") as Cli:
        ctx = Cli.return_value.__enter__.return_value
        ctx.request.return_value = _resp(403, {"error": "1010"})
        with pytest.raises(HTTPException) as ei:
            client.request("GET", "/watchlists")
    assert ei.value.status_code == 403


def test_drop_none_filters_none_values():
    from etoro_api.client import drop_none
    assert drop_none({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_client.py -v`
Expected: FAIL — `No module named 'etoro_api.client'`.

- [ ] **Step 3: Write `back/etoro_api/client.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add etoro_api/client.py tests/test_etoro_client.py
git commit -m "feat(quantiq): etoro http client with cloudflare UA + request-id"
```

---

### Task 5: Tenant dependency

**Files:**
- Create: `back/etoro_api/deps.py`
- Test: `back/tests/test_etoro_deps.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_deps.py
from unittest.mock import patch
import pytest
from fastapi import HTTPException


def test_uses_vault_credentials_when_present(monkeypatch):
    import etoro_api.deps as deps
    from etoro_api.vault import Credentials
    monkeypatch.setattr(deps.vault, "get_credentials",
                        lambda uid: Credentials("PUB", "USR", "demo"))
    client = deps.get_etoro_client(x_user_id="u1")
    assert client.public_key == "PUB"
    assert client.user_key == "USR"


def test_falls_back_to_env_when_no_row(monkeypatch):
    import etoro_api.deps as deps
    monkeypatch.setattr(deps.vault, "get_credentials", lambda uid: None)
    monkeypatch.setenv("ETORO_PUBLIC_KEY", "ENVPUB")
    monkeypatch.setenv("ETORO_PRIVATE_KEY", "ENVUSR")
    client = deps.get_etoro_client(x_user_id="u1")
    assert client.public_key == "ENVPUB"
    assert client.user_key == "ENVUSR"


def test_raises_when_no_creds_anywhere(monkeypatch):
    import etoro_api.deps as deps
    monkeypatch.setattr(deps.vault, "get_credentials", lambda uid: None)
    monkeypatch.delenv("ETORO_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ETORO_PRIVATE_KEY", raising=False)
    with pytest.raises(HTTPException) as ei:
        deps.get_etoro_client(x_user_id="u1")
    assert ei.value.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_deps.py -v`
Expected: FAIL — `No module named 'etoro_api.deps'`.

- [ ] **Step 3: Write `back/etoro_api/deps.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_deps.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add etoro_api/deps.py tests/test_etoro_deps.py
git commit -m "feat(quantiq): tenant dependency with vault + env fallback"
```

---

### Task 6: Settings router (`/etoro/credentials`)

**Files:**
- Create: `back/routers/etoro/__init__.py` (temporary, settings only — extended in Task 11), `back/routers/etoro/settings.py`
- Test: `back/tests/test_etoro_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_settings.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from routers.etoro import settings
    store = {}
    monkeypatch.setattr(settings.vault, "set_credentials",
                        lambda uid, pub, usr, env: store.update(
                            user_id=uid, public=pub, user=usr, env=env))
    monkeypatch.setattr(settings.vault, "get_credentials",
                        lambda uid: MagicMock(environment="demo", public_key="ABCD1234"))
    monkeypatch.setattr(settings.vault, "delete_credentials",
                        lambda uid: store.clear())
    app = FastAPI()
    app.include_router(settings.router)
    return TestClient(app), store


def test_post_credentials_stores(client):
    c, store = client
    r = c.post("/etoro/credentials",
               headers={"X-User-Id": "u1"},
               json={"public_key": "P", "user_key": "U", "environment": "demo"})
    assert r.status_code == 200
    assert store["public"] == "P" and store["env"] == "demo"


def test_get_status_masks_key(client):
    c, _ = client
    r = c.get("/etoro/credentials", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    body = r.json()
    assert body["has_keys"] is True
    assert body["public_key_last4"] == "1234"


def test_post_rejects_bad_environment(client):
    c, _ = client
    r = c.post("/etoro/credentials", headers={"X-User-Id": "u1"},
               json={"public_key": "P", "user_key": "U", "environment": "paper"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_settings.py -v`
Expected: FAIL — `No module named 'routers.etoro'`.

- [ ] **Step 3: Create the package + `settings.py`**

`back/routers/etoro/__init__.py` (temporary — replaced in Task 11):
```python
"""eToro router package."""
```

`back/routers/etoro/settings.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_settings.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add routers/etoro/__init__.py routers/etoro/settings.py tests/test_etoro_settings.py
git commit -m "feat(quantiq): /etoro/credentials settings router"
```

---

### Task 7: Market-data router

**Files:**
- Create: `back/routers/etoro/market_data.py`
- Test: `back/tests/test_etoro_market_data.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_market_data.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routers.etoro import market_data
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(market_data.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_search_passthrough(client):
    c, fake = client
    r = c.get("/etoro/market-data/search",
              params={"fields": "instrumentId,displayname", "searchText": "BTC"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/market-data/search"
    assert fake.request.call_args.kwargs["params"] == {
        "fields": "instrumentId,displayname", "searchText": "BTC"}


def test_candles_passthrough_builds_path(client):
    c, fake = client
    r = c.get("/etoro/market-data/instruments/100000/history/candles/desc/OneDay/50")
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/market-data/instruments/100000/history/candles/desc/OneDay/50"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_market_data.py -v`
Expected: FAIL — cannot import `market_data`.

- [ ] **Step 3: Write `back/routers/etoro/market_data.py`**

```python
"""eToro market-data endpoints (search, instruments, rates, candles, reference)."""
from typing import Optional
from fastapi import APIRouter, Depends

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro/market-data", tags=["etoro:market-data"])


@router.get("/search")
def search(fields: str, searchText: Optional[str] = None,
           internalSymbolFull: Optional[str] = None,
           pageSize: Optional[int] = None, pageNumber: Optional[int] = None,
           sort: Optional[str] = None,
           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/search", params=drop_none({
        "fields": fields, "searchText": searchText,
        "internalSymbolFull": internalSymbolFull,
        "pageSize": pageSize, "pageNumber": pageNumber, "sort": sort}))


@router.get("/instruments")
def instruments(instrumentIds: Optional[str] = None, exchangeIds: Optional[str] = None,
                stocksIndustryIds: Optional[str] = None, instrumentTypeIds: Optional[str] = None,
                client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instruments", params=drop_none({
        "instrumentIds": instrumentIds, "exchangeIds": exchangeIds,
        "stocksIndustryIds": stocksIndustryIds, "instrumentTypeIds": instrumentTypeIds}))


@router.get("/instruments/rates")
def rates(instrumentIds: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instruments/rates",
                          params={"instrumentIds": instrumentIds})


@router.get("/instruments/history/closing-price")
def closing_price(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instruments/history/closing-price")


@router.get("/instruments/{instrument_id}/history/candles/{direction}/{interval}/{candles_count}")
def candles(instrument_id: int, direction: str, interval: str, candles_count: int,
            client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "GET",
        f"/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{candles_count}")


@router.get("/exchanges")
def exchanges(exchangeIds: Optional[str] = None,
              client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/exchanges",
                          params=drop_none({"exchangeIds": exchangeIds}))


@router.get("/instrument-types")
def instrument_types(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/instrument-types")


@router.get("/stocks-industries")
def stocks_industries(stocksIndustryIds: Optional[str] = None,
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/market-data/stocks-industries",
                          params=drop_none({"stocksIndustryIds": stocksIndustryIds}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_market_data.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add routers/etoro/market_data.py tests/test_etoro_market_data.py
git commit -m "feat(quantiq): etoro market-data router"
```

---

### Task 8: Trading router (+ real-execution guard)

**Files:**
- Create: `back/routers/etoro/trading.py`
- Test: `back/tests/test_etoro_trading.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_trading.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false")
    from routers.etoro import trading
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(trading.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_demo_open_by_amount_passthrough(client):
    c, fake = client
    body = {"InstrumentID": 100000, "IsBuy": True, "Leverage": 1, "Amount": 100}
    r = c.post("/etoro/trading/execution/demo/market-open-orders/by-amount",
               headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200 and r.json() == {"ok": True}
    method, path = fake.request.call_args.args
    assert method == "POST"
    assert path == "/trading/execution/demo/market-open-orders/by-amount"
    assert fake.request.call_args.kwargs["json"] == body


def test_real_execution_blocked_when_flag_off(client):
    c, fake = client
    r = c.post("/etoro/trading/execution/market-open-orders/by-amount",
               headers={"X-User-Id": "u1"},
               json={"InstrumentID": 1, "IsBuy": True, "Leverage": 1, "Amount": 100})
    assert r.status_code == 403
    assert fake.request.call_count == 0  # never reached eToro


def test_real_execution_allowed_when_flag_on(client, monkeypatch):
    c, fake = client
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "true")
    r = c.post("/etoro/trading/execution/market-open-orders/by-amount",
               headers={"X-User-Id": "u1"},
               json={"InstrumentID": 1, "IsBuy": True, "Leverage": 1, "Amount": 100})
    assert r.status_code == 200


def test_info_portfolio_passthrough(client):
    c, fake = client
    r = c.get("/etoro/trading/info/demo/portfolio", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/trading/info/demo/portfolio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_trading.py -v`
Expected: FAIL — cannot import `trading`.

- [ ] **Step 3: Write `back/routers/etoro/trading.py`**

```python
"""eToro trading endpoints: execution (demo + real) and portfolio/PnL info.

Real-money execution (paths without /demo/) is gated behind the
QUANTIQ_ALLOW_REAL_EXECUTION env flag (default off → 403).
"""
import os
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro/trading", tags=["etoro:trading"])


def _guard_real() -> None:
    if os.getenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false").lower() not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=403,
            detail="real-money execution disabled. Set QUANTIQ_ALLOW_REAL_EXECUTION=true to enable.")


# ---------------- Demo execution ----------------

@router.post("/execution/demo/market-open-orders/by-amount")
def demo_open_by_amount(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/trading/execution/demo/market-open-orders/by-amount", json=body)


@router.post("/execution/demo/market-open-orders/by-units")
def demo_open_by_units(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/trading/execution/demo/market-open-orders/by-units", json=body)


@router.delete("/execution/demo/market-open-orders/{order_id}")
def demo_cancel_open(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/trading/execution/demo/market-open-orders/{order_id}")


@router.post("/execution/demo/market-close-orders/positions/{position_id}")
def demo_close_position(position_id: str, body: dict = Body(...),
                        client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", f"/trading/execution/demo/market-close-orders/positions/{position_id}", json=body)


@router.delete("/execution/demo/market-close-orders/{order_id}")
def demo_cancel_close(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/trading/execution/demo/market-close-orders/{order_id}")


@router.post("/execution/demo/limit-orders")
def demo_limit_open(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/trading/execution/demo/limit-orders", json=body)


@router.delete("/execution/demo/limit-orders/{order_id}")
def demo_limit_cancel(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/trading/execution/demo/limit-orders/{order_id}")


# ---------------- Real execution (guarded) ----------------

@router.post("/execution/market-open-orders/by-amount")
def real_open_by_amount(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", "/trading/execution/market-open-orders/by-amount", json=body)


@router.post("/execution/market-open-orders/by-units")
def real_open_by_units(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", "/trading/execution/market-open-orders/by-units", json=body)


@router.delete("/execution/market-open-orders/{order_id}")
def real_cancel_open(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("DELETE", f"/trading/execution/market-open-orders/{order_id}")


@router.post("/execution/market-close-orders/positions/{position_id}")
def real_close_position(position_id: str, body: dict = Body(...),
                        client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", f"/trading/execution/market-close-orders/positions/{position_id}", json=body)


@router.delete("/execution/market-close-orders/{order_id}")
def real_cancel_close(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("DELETE", f"/trading/execution/market-close-orders/{order_id}")


@router.post("/execution/limit-orders")
def real_limit_open(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("POST", "/trading/execution/limit-orders", json=body)


@router.delete("/execution/limit-orders/{order_id}")
def real_limit_cancel(order_id: str, client: EtoroClient = Depends(get_etoro_client)):
    _guard_real()
    return client.request("DELETE", f"/trading/execution/limit-orders/{order_id}")


# ---------------- Info & portfolio ----------------

@router.get("/info/demo/pnl")
def demo_pnl(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/demo/pnl")


@router.get("/info/real/pnl")
def real_pnl(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/real/pnl")


@router.get("/info/demo/portfolio")
def demo_portfolio(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/demo/portfolio")


@router.get("/info/portfolio")
def real_portfolio(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/portfolio")


@router.get("/info/trade/history")
def trade_history(minDate: str, page: Optional[int] = None, pageSize: Optional[int] = None,
                  client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/trading/info/trade/history", params=drop_none({
        "minDate": minDate, "page": page, "pageSize": pageSize}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_trading.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add routers/etoro/trading.py tests/test_etoro_trading.py
git commit -m "feat(quantiq): etoro trading router with real-execution guard"
```

---

### Task 9: Social router (feeds, watchlists, user-info, lists)

**Files:**
- Create: `back/routers/etoro/social.py`
- Test: `back/tests/test_etoro_social.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_social.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routers.etoro import social
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(social.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_list_watchlists_passthrough(client):
    c, fake = client
    r = c.get("/etoro/watchlists", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/watchlists"


def test_create_watchlist_uses_query_params(client):
    c, fake = client
    r = c.post("/etoro/watchlists", headers={"X-User-Id": "u1"},
               params={"name": "Tech"})
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/watchlists"
    assert fake.request.call_args.kwargs["params"] == {"name": "Tech"}


def test_post_feed_passthrough(client):
    c, fake = client
    r = c.post("/etoro/feeds/post", headers={"X-User-Id": "u1"},
               json={"message": "hi"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "POST" and path == "/feeds/post"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_social.py -v`
Expected: FAIL — cannot import `social`.

- [ ] **Step 3: Write `back/routers/etoro/social.py`**

```python
"""eToro social endpoints: feeds, watchlists, curated lists, recommendations,
copiers, and user-info / analytics."""
from typing import Optional
from fastapi import APIRouter, Body, Depends

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro", tags=["etoro:social"])


# ---------------- Feeds ----------------

@router.get("/feeds/instrument/{market_id}")
def feed_instrument(market_id: str, requesterUserId: Optional[int] = None,
                    take: Optional[int] = None, offset: Optional[int] = None,
                    client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/feeds/instrument/{market_id}", params=drop_none({
        "requesterUserId": requesterUserId, "take": take, "offset": offset}))


@router.get("/feeds/user/{user_id}")
def feed_user(user_id: int, requesterUserId: Optional[int] = None,
              take: Optional[int] = None, offset: Optional[int] = None,
              client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/feeds/user/{user_id}", params=drop_none({
        "requesterUserId": requesterUserId, "take": take, "offset": offset}))


@router.post("/feeds/post")
def feed_post(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/feeds/post", json=body)


# ---------------- Watchlists ----------------

@router.get("/watchlists")
def list_watchlists(itemsPerPageForSingle: Optional[int] = None,
                    ensureBuiltinWatchlists: Optional[bool] = None,
                    addRelatedAssets: Optional[bool] = None,
                    client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/watchlists", params=drop_none({
        "itemsPerPageForSingle": itemsPerPageForSingle,
        "ensureBuiltinWatchlists": ensureBuiltinWatchlists,
        "addRelatedAssets": addRelatedAssets}))


@router.get("/watchlists/{watchlist_id}")
def get_watchlist(watchlist_id: str, pageNumber: Optional[int] = None,
                  itemsPerPage: Optional[int] = None,
                  client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/watchlists/{watchlist_id}", params=drop_none({
        "pageNumber": pageNumber, "itemsPerPage": itemsPerPage}))


@router.post("/watchlists")
def create_watchlist(name: str, type: Optional[str] = None,
                     dynamicQuery: Optional[str] = None,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/watchlists", params=drop_none({
        "name": name, "type": type, "dynamicQuery": dynamicQuery}))


@router.put("/watchlists/{watchlist_id}")
def rename_watchlist(watchlist_id: str, newName: str,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("PUT", f"/watchlists/{watchlist_id}", params={"newName": newName})


@router.delete("/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/watchlists/{watchlist_id}")


@router.post("/watchlists/{watchlist_id}/items")
def add_watchlist_items(watchlist_id: str, body: list = Body(...),
                        client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", f"/watchlists/{watchlist_id}/items", json=body)


@router.put("/watchlists/{watchlist_id}/items")
def update_watchlist_items(watchlist_id: str, body: list = Body(...),
                           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("PUT", f"/watchlists/{watchlist_id}/items", json=body)


@router.delete("/watchlists/{watchlist_id}/items")
def delete_watchlist_items(watchlist_id: str, body: list = Body(...),
                           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/watchlists/{watchlist_id}/items", json=body)


@router.get("/watchlists/public/{user_id}")
def public_watchlists(user_id: int, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/watchlists/public/{user_id}")


@router.get("/watchlists/public/{user_id}/{watchlist_id}")
def public_watchlist(user_id: int, watchlist_id: str,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/watchlists/public/{user_id}/{watchlist_id}")


# ---------------- Curated lists & recommendations ----------------

@router.get("/curated-lists")
def curated_lists(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/curated-lists")


@router.get("/market-recommendations/{items_count}")
def market_recommendations(items_count: int,
                           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/market-recommendations/{items_count}")


# ---------------- Popular investors ----------------

@router.get("/pi-data/copiers")
def copiers(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/pi-data/copiers")


# ---------------- User info & analytics ----------------

@router.get("/user-info/people")
def people(usernames: Optional[str] = None, cidList: Optional[str] = None,
           client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/user-info/people", params=drop_none({
        "usernames": usernames, "cidList": cidList}))


@router.get("/user-info/people/search")
def people_search(period: str, page: Optional[int] = None, pageSize: Optional[int] = None,
                  sort: Optional[str] = None, popularInvestor: Optional[bool] = None,
                  client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/user-info/people/search", params=drop_none({
        "period": period, "page": page, "pageSize": pageSize, "sort": sort,
        "popularInvestor": popularInvestor}))


@router.get("/user-info/people/{username}/gain")
def people_gain(username: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/gain")


@router.get("/user-info/people/{username}/daily-gain")
def people_daily_gain(username: str, minDate: str, maxDate: str, type: str,
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/daily-gain", params={
        "minDate": minDate, "maxDate": maxDate, "type": type})


@router.get("/user-info/people/{username}/portfolio/live")
def people_portfolio_live(username: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/portfolio/live")


@router.get("/user-info/people/{username}/tradeinfo")
def people_tradeinfo(username: str, period: str,
                     client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/user-info/people/{username}/tradeinfo",
                          params={"period": period})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_social.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add routers/etoro/social.py tests/test_etoro_social.py
git commit -m "feat(quantiq): etoro social router (feeds, watchlists, user-info)"
```

---

### Task 10: Agent-portfolios router

**Files:**
- Create: `back/routers/etoro/agent_portfolios.py`
- Test: `back/tests/test_etoro_agent_portfolios.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_agent_portfolios.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from routers.etoro import agent_portfolios
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(agent_portfolios.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_list_sub_portfolios(client):
    c, fake = client
    r = c.get("/etoro/sub-portfolios", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/sub-portfolios"


def test_create_sub_portfolio_passthrough_body(client):
    c, fake = client
    body = {"investmentAmountInUsd": 2000, "subPortfolioName": "alpha1",
            "userTokenName": "tok", "scopeIds": [201]}
    r = c.post("/etoro/sub-portfolios", headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200
    assert fake.request.call_args.kwargs["json"] == body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_agent_portfolios.py -v`
Expected: FAIL — cannot import `agent_portfolios`.

- [ ] **Step 3: Write `back/routers/etoro/agent_portfolios.py`**

```python
"""eToro agent sub-portfolios (copy-trading sub-accounts) + user tokens."""
from fastapi import APIRouter, Body, Depends

from etoro_api.client import EtoroClient
from etoro_api.deps import get_etoro_client

router = APIRouter(prefix="/etoro/sub-portfolios", tags=["etoro:agent-portfolios"])


@router.get("")
def list_sub_portfolios(client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/sub-portfolios")


@router.post("")
def create_sub_portfolio(body: dict = Body(...), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", "/sub-portfolios", json=body)


@router.delete("/{sub_portfolio_id}")
def delete_sub_portfolio(sub_portfolio_id: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("DELETE", f"/sub-portfolios/{sub_portfolio_id}")


@router.post("/{sub_portfolio_id}/user-tokens")
def create_user_token(sub_portfolio_id: str, body: dict = Body(...),
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request("POST", f"/sub-portfolios/{sub_portfolio_id}/user-tokens", json=body)


@router.patch("/{sub_portfolio_id}/user-tokens/{user_token_id}")
def update_user_token(sub_portfolio_id: str, user_token_id: str, body: dict = Body(...),
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "PATCH", f"/sub-portfolios/{sub_portfolio_id}/user-tokens/{user_token_id}", json=body)


@router.delete("/{sub_portfolio_id}/user-tokens/{user_token_id}")
def delete_user_token(sub_portfolio_id: str, user_token_id: str,
                      client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "DELETE", f"/sub-portfolios/{sub_portfolio_id}/user-tokens/{user_token_id}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_agent_portfolios.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add routers/etoro/agent_portfolios.py tests/test_etoro_agent_portfolios.py
git commit -m "feat(quantiq): etoro agent sub-portfolios router"
```

---

### Task 11: Aggregate sub-routers + wire into main.py

**Files:**
- Modify: `back/routers/etoro/__init__.py`, `back/main.py`
- Test: `back/tests/test_etoro_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_wiring.py
def test_aggregated_router_exposes_all_subrouters():
    from routers.etoro import router
    paths = {r.path for r in router.routes}
    # one representative path per sub-router
    assert "/etoro/credentials" in paths
    assert "/etoro/market-data/search" in paths
    assert "/etoro/trading/info/demo/portfolio" in paths
    assert "/etoro/watchlists" in paths
    assert "/etoro/sub-portfolios" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_wiring.py -v`
Expected: FAIL — `router` not exported from `routers.etoro` (the `__init__.py` is still the placeholder).

- [ ] **Step 3: Replace `back/routers/etoro/__init__.py`**

```python
"""Aggregate eToro sub-routers into a single router mounted under /etoro."""
from fastapi import APIRouter

from routers.etoro import (
    settings,
    market_data,
    trading,
    social,
    agent_portfolios,
)

router = APIRouter()
router.include_router(settings.router)
router.include_router(market_data.router)
router.include_router(trading.router)
router.include_router(social.router)
router.include_router(agent_portfolios.router)
```

- [ ] **Step 4: Wire into `back/main.py`**

Add to the imports block (after `from routers import (...)`), a separate import:
```python
from routers import etoro
```
And add this line next to the other `app.include_router(...)` calls:
```python
app.include_router(etoro.router)
```
Also add `"etoro"` to the `categories` list in the `root()` handler.

- [ ] **Step 5: Run the wiring test + confirm the app imports**

Run: `python -m pytest tests/test_etoro_wiring.py -v`
Expected: PASS.

Run: `python -c "import main; print('app ok', any(getattr(r, 'path', '').startswith('/etoro') for r in main.app.routes))"`
Expected: prints `app ok True` (no traceback; requires MASSIVE_KEY present in back/.env, which it is).

- [ ] **Step 6: Commit**

```bash
git add routers/etoro/__init__.py main.py tests/test_etoro_wiring.py
git commit -m "feat(quantiq): mount aggregated etoro router in main app"
```

---

### Task 12: Full suite + live integration smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the whole back/ offline suite**

Run (from `back/`): `python -m pytest tests/ -v`
Expected: all PASS — existing tests plus the new eToro tests (supabase_client, vault, client, deps, settings, market_data, trading, social, agent_portfolios, wiring).

- [ ] **Step 2: Start the API**

Run (from `back/`): `python -m uvicorn main:app --reload --port 8765` (leave running in another shell).
Open `http://127.0.0.1:8765/docs` — confirm the `etoro:*` tag groups appear.

- [ ] **Step 3: Live keyless-tenant smoke (uses back/.env demo keys via fallback)**

With Supabase running (`npx supabase start`) and the API up, run:
```bash
curl -s -H "X-User-Id: 11111111-1111-1111-1111-111111111111" \
  "http://127.0.0.1:8765/etoro/market-data/search?fields=instrumentId,internalSymbolFull,displayname&internalSymbolFull=BTC"
```
Expected: HTTP 200 with eToro instrument JSON (served via the `.env` ETORO_* fallback because the vault has no row for that user yet).

- [ ] **Step 4: Live vault round-trip smoke**

Store keys for a tenant, then read status:
```bash
curl -s -X POST -H "X-User-Id: 22222222-2222-2222-2222-222222222222" \
  -H "Content-Type: application/json" \
  -d "{\"public_key\":\"<ETORO_PUBLIC_KEY>\",\"user_key\":\"<ETORO_PRIVATE_KEY>\",\"environment\":\"demo\"}" \
  http://127.0.0.1:8765/etoro/credentials

curl -s -H "X-User-Id: 22222222-2222-2222-2222-222222222222" \
  http://127.0.0.1:8765/etoro/credentials
```
Expected: first returns `{"status":"ok","environment":"demo"}`; second returns `{"has_keys":true,"environment":"demo","public_key_last4":"..."}`. Then the same tenant can call `/etoro/trading/info/demo/portfolio` and get a 200.

> If offline, Steps 2–4 are skipped (they need network + Docker/Supabase). The offline suite in Step 1 is the gating check.

- [ ] **Step 5: Commit (if any .env.example tweaks were needed)**

```bash
git add -A
git commit -m "chore(quantiq): verify etoro router end-to-end"
```

---

## Self-Review notes

- **Spec coverage:** Supabase local + migration/RLS (Task 1), supabase-py client (Task 2), Fernet vault (Task 3), EtoroClient w/ Cloudflare UA + request-id (Task 4), tenant dependency + dev fallback (Task 5), `/etoro/credentials` settings (Task 6), market-data (7), trading + real-exec guard (8), social/feeds/watchlists/user-info (9), agent sub-portfolios (10), wiring into main (11), dependencies + smoke (1/12). ✓ All spec sections mapped.
- **Type/name consistency:** `EtoroClient(public_key, user_key, *, environment)` and `.request(method, path, *, params, json)` used identically across deps + all routers; `drop_none` imported from `etoro_api.client` everywhere; `vault.get_credentials/set_credentials/delete_credentials` signatures match across vault, deps, settings; `get_etoro_client` overridden via `app.dependency_overrides` in every router test. ✓
- **Placeholders:** none — every code step is complete. The only deferred items are explicitly out-of-scope (JWT auth, frontend) per the spec.
- **Safety:** real-money execution gated behind `QUANTIQ_ALLOW_REAL_EXECUTION` (Task 8), tested both ways. Current keys are demo regardless.
```
