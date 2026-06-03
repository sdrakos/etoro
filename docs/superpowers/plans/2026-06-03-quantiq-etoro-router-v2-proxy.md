# eToro router v2 — proxy + typed core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the drifted hand-written eToro sub-routers with a generic passthrough proxy (covers all v1+v2 eToro endpoints) plus a small set of typed convenience endpoints for the core trading actions.

**Architecture:** `EtoroClient` becomes host-based and takes full `/api/vN/...` paths. A `proxy.py` catch-all forwards `/etoro/api/{v1,v2}/{path}` to eToro (with a real-execution guard). A `core.py` exposes ~8 typed endpoints (search+enrich, candles, rates, orders v2, close, portfolio, pnl, history). The four broad routers (market_data, trading, social, agent_portfolios) and their tests are deleted; `settings.py`, vault, deps, supabase are untouched.

**Tech Stack:** Python 3.11+, FastAPI, httpx, Pydantic, pytest. The authoritative eToro spec is committed at `back/etoro_api/reference/etoro-openapi.json`.

All commands assume cwd `etoro/back/` unless noted. Tests offline (httpx mocked). Clean commits, **no** Co-Authored-By trailer.

---

## File Structure

| File | Responsibility |
|---|---|
| `back/etoro_api/client.py` | host base URL; `request(method, full_path, ...)` |
| `back/etoro_api/models.py` | `UnifiedOrderRequest`, `ClosePositionRequest` (new) |
| `back/etoro_api/reference/etoro-openapi.json` | official spec (already saved; committed in Task 2) |
| `back/routers/etoro/proxy.py` | generic passthrough + guard helpers (new) |
| `back/routers/etoro/core.py` | typed convenience endpoints (new) |
| `back/routers/etoro/__init__.py` | aggregate settings + core + proxy |
| `back/routers/etoro/{market_data,trading,social,agent_portfolios}.py` | **deleted** |
| `back/tests/test_etoro_{market_data,trading,social,agent_portfolios}.py` | **deleted** |
| `back/tests/test_etoro_models.py`, `test_etoro_proxy.py`, `test_etoro_core.py` | new |
| `back/tests/test_etoro_client.py`, `test_etoro_wiring.py` | updated |

Task order keeps the suite green at every step: models → (client change + delete old routers, atomic) → proxy → core+wiring → verify.

---

### Task 1: Order/close request models

**Files:**
- Create: `back/etoro_api/models.py`, `back/tests/test_etoro_models.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_models.py
import pytest
from pydantic import ValidationError


def test_unified_order_requires_action_and_transaction():
    from etoro_api.models import UnifiedOrderRequest
    with pytest.raises(ValidationError):
        UnifiedOrderRequest(transaction="buy")  # missing action
    with pytest.raises(ValidationError):
        UnifiedOrderRequest(action="open")  # missing transaction


def test_unified_order_exclude_none_drops_optionals():
    from etoro_api.models import UnifiedOrderRequest
    m = UnifiedOrderRequest(action="open", transaction="buy",
                            instrumentId=100000, amount=100, leverage=1)
    body = m.model_dump(exclude_none=True)
    assert body == {"action": "open", "transaction": "buy",
                    "instrumentId": 100000, "amount": 100, "leverage": 1}
    assert "symbol" not in body and "units" not in body


def test_close_position_model():
    from etoro_api.models import ClosePositionRequest
    full = ClosePositionRequest(InstrumentID=100000)
    assert full.model_dump(exclude_none=True) == {"InstrumentID": 100000}
    partial = ClosePositionRequest(InstrumentID=100000, UnitsToDeduct=2.5)
    assert partial.model_dump(exclude_none=True) == {"InstrumentID": 100000, "UnitsToDeduct": 2.5}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_models.py -v`
Expected: FAIL — `No module named 'etoro_api.models'`.

- [ ] **Step 3: Write `back/etoro_api/models.py`**

```python
"""Typed request models for the core eToro trading actions (from the official spec)."""
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel


class UnifiedOrderRequest(BaseModel):
    """eToro v2 UnifiedOrderRequest. Only `action` and `transaction` are required;
    send the rest as needed. Serialize with model_dump(exclude_none=True)."""
    action: str
    transaction: str
    symbol: Optional[str] = None
    instrumentId: Optional[int] = None
    settlementType: Optional[str] = None
    orderType: Optional[str] = None
    triggerRate: Optional[float] = None
    leverage: Optional[int] = None
    amount: Optional[float] = None
    orderCurrency: Optional[str] = None
    units: Optional[float] = None
    contracts: Optional[float] = None
    stopLossRate: Optional[float] = None
    takeProfitRate: Optional[float] = None
    stopLossType: Optional[str] = None
    additionalMargin: Optional[float] = None
    positionIds: Optional[List[Any]] = None


class ClosePositionRequest(BaseModel):
    """eToro market-close-orders body (PascalCase per spec)."""
    InstrumentID: int
    UnitsToDeduct: Optional[float] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add back/etoro_api/models.py back/tests/test_etoro_models.py
git commit -m "feat(quantiq): typed order/close request models from official spec"
```

---

### Task 2: Client → host base, and remove the drifted routers (atomic)

**Files:**
- Modify: `back/etoro_api/client.py`, `back/tests/test_etoro_client.py`, `back/routers/etoro/__init__.py`, `back/tests/test_etoro_wiring.py`
- Delete: `back/routers/etoro/{market_data,trading,social,agent_portfolios}.py`, `back/tests/test_etoro_{market_data,trading,social,agent_portfolios}.py`
- Add (commit): `back/etoro_api/reference/etoro-openapi.json` (already present in the working tree)

> Why atomic: changing the client base breaks the old routers (they pass `/market-data/...` without `/api/v1`). Deleting them in the same task keeps the suite green.

- [ ] **Step 1: Update `back/tests/test_etoro_client.py`**

Replace its contents so paths are full and the URL is asserted:

```python
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


def test_request_uses_host_base_and_full_path():
    from etoro_api.client import EtoroClient, BASE_URL
    assert BASE_URL == "https://public-api.etoro.com"
    client = EtoroClient("PUB", "USR")
    with patch("etoro_api.client.httpx.Client") as Cli:
        ctx = Cli.return_value.__enter__.return_value
        ctx.request.return_value = _resp(200, {"ok": True})
        out = client.request("GET", "/api/v2/trading/info/orders:lookup", params={"a": 1})
    assert out == {"ok": True}
    args, kwargs = ctx.request.call_args
    assert args[0] == "GET"
    assert args[1] == "https://public-api.etoro.com/api/v2/trading/info/orders:lookup"
    h = kwargs["headers"]
    assert h["x-api-key"] == "PUB" and h["x-user-key"] == "USR"
    assert h["User-Agent"].startswith("Mozilla/")
    assert len(h["x-request-id"]) >= 8


def test_request_raises_httpexception_on_error_status():
    from etoro_api.client import EtoroClient
    client = EtoroClient("PUB", "USR")
    with patch("etoro_api.client.httpx.Client") as Cli:
        ctx = Cli.return_value.__enter__.return_value
        ctx.request.return_value = _resp(403, {"error": "1010"})
        with pytest.raises(HTTPException) as ei:
            client.request("GET", "/api/v1/watchlists")
    assert ei.value.status_code == 403


def test_drop_none_filters_none_values():
    from etoro_api.client import drop_none
    assert drop_none({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_etoro_client.py -v`
Expected: FAIL — `BASE_URL` still ends with `/api/v1` (assertion fails) and the URL assertion fails.

- [ ] **Step 3: Change the base URL in `back/etoro_api/client.py`**

Change exactly this line:

```python
BASE_URL = "https://public-api.etoro.com/api/v1"
```
to:
```python
BASE_URL = "https://public-api.etoro.com"
```

Nothing else in `client.py` changes — `request()` already does `url = BASE_URL + path`, so callers now pass the full `/api/vN/...` path.

- [ ] **Step 4: Delete the four drifted routers and their tests**

```bash
git rm back/routers/etoro/market_data.py back/routers/etoro/trading.py \
       back/routers/etoro/social.py back/routers/etoro/agent_portfolios.py \
       back/tests/test_etoro_market_data.py back/tests/test_etoro_trading.py \
       back/tests/test_etoro_social.py back/tests/test_etoro_agent_portfolios.py
```

- [ ] **Step 5: Reduce the aggregator to settings-only (temporary)**

Replace `back/routers/etoro/__init__.py` with:

```python
"""Aggregate eToro sub-routers into a single router mounted under /etoro."""
from fastapi import APIRouter

from routers.etoro import settings

router = APIRouter()
router.include_router(settings.router)
```

- [ ] **Step 6: Update `back/tests/test_etoro_wiring.py` to the temporary state**

Replace its contents with:

```python
def test_aggregated_router_exposes_settings():
    from routers.etoro import router
    paths = {r.path for r in router.routes}
    assert "/etoro/credentials" in paths
```

- [ ] **Step 7: Run the full suite green**

Run: `python -m pytest tests/ -q`
Expected: all PASS (existing back tests + supabase_client + vault + client + deps + settings + models + wiring). The 4 deleted router test files are gone, so no failures from them.

Also confirm the app imports:
Run: `python -c "import main; print('ok')"`
Expected: `ok` (no traceback).

- [ ] **Step 8: Commit**

```bash
git add back/etoro_api/client.py back/etoro_api/reference/etoro-openapi.json \
        back/routers/etoro/__init__.py back/tests/test_etoro_client.py back/tests/test_etoro_wiring.py
git commit -m "refactor(quantiq): host-based etoro client; remove drifted routers; commit official spec"
```

---

### Task 3: Generic proxy

**Files:**
- Create: `back/routers/etoro/proxy.py`, `back/tests/test_etoro_proxy.py`
- Modify: `back/routers/etoro/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_proxy.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false")
    from routers.etoro import proxy
    from etoro_api.deps import get_etoro_client
    fake = MagicMock()
    fake.request.return_value = {"ok": True}
    app = FastAPI()
    app.include_router(proxy.router)
    app.dependency_overrides[get_etoro_client] = lambda: fake
    return TestClient(app), fake


def test_forwards_v1_path_and_query(client):
    c, fake = client
    r = c.get("/etoro/api/v1/market-data/exchanges", params={"exchangeIds": "4"},
              headers={"X-User-Id": "u1"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    method, path = fake.request.call_args.args
    assert method == "GET" and path == "/api/v1/market-data/exchanges"
    assert fake.request.call_args.kwargs["params"] == {"exchangeIds": "4"}


def test_forwards_v2_post_body(client):
    c, fake = client
    body = {"action": "open", "transaction": "buy", "instrumentId": 100000, "amount": 100}
    r = c.post("/etoro/api/v2/trading/execution/demo/orders",
               headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "POST" and path == "/api/v2/trading/execution/demo/orders"
    assert fake.request.call_args.kwargs["json"] == body


def test_unknown_version_404(client):
    c, fake = client
    r = c.get("/etoro/api/v3/anything", headers={"X-User-Id": "u1"})
    assert r.status_code == 404
    assert fake.request.call_count == 0


def test_real_execution_blocked_when_flag_off(client):
    c, fake = client
    r = c.post("/etoro/api/v2/trading/execution/orders",  # no /demo/
               headers={"X-User-Id": "u1"}, json={"action": "open"})
    assert r.status_code == 403
    assert fake.request.call_count == 0


def test_demo_execution_allowed_when_flag_off(client):
    c, fake = client
    r = c.post("/etoro/api/v2/trading/execution/demo/orders",
               headers={"X-User-Id": "u1"}, json={"action": "open"})
    assert r.status_code == 200
    assert fake.request.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_proxy.py -v`
Expected: FAIL — `No module named 'routers.etoro.proxy'`.

- [ ] **Step 3: Write `back/routers/etoro/proxy.py`**

```python
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
```

- [ ] **Step 4: Add the proxy to the aggregator**

Edit `back/routers/etoro/__init__.py` to import and include `proxy` (keep `settings`):

```python
"""Aggregate eToro sub-routers into a single router mounted under /etoro."""
from fastapi import APIRouter

from routers.etoro import settings, proxy

router = APIRouter()
router.include_router(settings.router)
router.include_router(proxy.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_etoro_proxy.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add back/routers/etoro/proxy.py back/routers/etoro/__init__.py back/tests/test_etoro_proxy.py
git commit -m "feat(quantiq): generic eToro proxy (v1+v2) with real-execution guard"
```

---

### Task 4: Typed core endpoints + final wiring

**Files:**
- Create: `back/routers/etoro/core.py`, `back/tests/test_etoro_core.py`
- Modify: `back/routers/etoro/__init__.py`, `back/tests/test_etoro_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# back/tests/test_etoro_core.py
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def make_client():
    def _make(side_effect=None, return_value=None):
        from routers.etoro import core
        from etoro_api.deps import get_etoro_client
        fake = MagicMock()
        if side_effect is not None:
            fake.request.side_effect = side_effect
        else:
            fake.request.return_value = return_value if return_value is not None else {"ok": True}
        app = FastAPI()
        app.include_router(core.router)
        app.dependency_overrides[get_etoro_client] = lambda: fake
        return TestClient(app), fake
    return _make


def test_search_enriches_with_names(make_client):
    search_res = {"items": [{"instrumentId": 100000}, {"instrumentId": 100134}]}
    meta_res = {"instrumentDisplayDatas": [
        {"instrumentID": 100000, "instrumentDisplayName": "Bitcoin",
         "instrumentTypeID": 10, "exchangeID": 8},
        {"instrumentID": 100134, "instrumentDisplayName": "Bitcoin Cash",
         "instrumentTypeID": 10, "exchangeID": 8}]}
    c, fake = make_client(side_effect=[search_res, meta_res])
    r = c.get("/etoro/search", params={"symbol": "BTC"}, headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0] == {"instrumentId": 100000, "name": "Bitcoin", "typeId": 10, "exchangeId": 8}
    # first call = search with searchText+fields; second = instruments with the ids
    first, second = fake.request.call_args_list
    assert first.args == ("GET", "/api/v1/market-data/search")
    assert first.kwargs["params"] == {"searchText": "BTC", "fields": "instrumentId"}
    assert second.args == ("GET", "/api/v1/market-data/instruments")
    assert second.kwargs["params"] == {"instrumentIds": "100000,100134"}


def test_candles_builds_path(make_client):
    c, fake = make_client(return_value={"candles": []})
    r = c.get("/etoro/candles/100000", params={"interval": "OneDay", "count": 30, "direction": "desc"},
              headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    _, path = fake.request.call_args.args
    assert path == "/api/v1/market-data/instruments/100000/history/candles/desc/OneDay/30"


def test_create_order_demo_v2_path_and_excludes_none(make_client):
    c, fake = make_client(return_value={"orderId": 1})
    body = {"action": "open", "transaction": "buy", "instrumentId": 100000,
            "amount": 100, "leverage": 1}
    r = c.post("/etoro/orders", params={"account": "demo"}, headers={"X-User-Id": "u1"}, json=body)
    assert r.status_code == 200
    method, path = fake.request.call_args.args
    assert method == "POST" and path == "/api/v2/trading/execution/demo/orders"
    sent = fake.request.call_args.kwargs["json"]
    assert sent == body and "symbol" not in sent  # exclude_none dropped optionals


def test_create_order_real_blocked_when_flag_off(make_client, monkeypatch):
    monkeypatch.setenv("QUANTIQ_ALLOW_REAL_EXECUTION", "false")
    c, fake = make_client(return_value={"orderId": 1})
    r = c.post("/etoro/orders", params={"account": "real"}, headers={"X-User-Id": "u1"},
               json={"action": "open", "transaction": "buy", "instrumentId": 1, "amount": 10})
    assert r.status_code == 403
    assert fake.request.call_count == 0


def test_portfolio_and_pnl_paths(make_client):
    c, fake = make_client(return_value={"ok": True})
    c.get("/etoro/portfolio", params={"account": "demo"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/trading/info/demo/portfolio"
    c.get("/etoro/portfolio", params={"account": "real"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/trading/info/portfolio"
    c.get("/etoro/pnl", params={"account": "real"}, headers={"X-User-Id": "u1"})
    assert fake.request.call_args.args[1] == "/api/v1/trading/info/real/pnl"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etoro_core.py -v`
Expected: FAIL — `No module named 'routers.etoro.core'`.

- [ ] **Step 3: Write `back/routers/etoro/core.py`**

```python
"""Typed convenience endpoints for the common eToro trading actions.

These are friendly, self-documented shortcuts; anything else is reachable via the
generic proxy. `account` selects demo (default) or real; real execution is guarded.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from etoro_api.client import EtoroClient, drop_none
from etoro_api.deps import get_etoro_client
from etoro_api.models import UnifiedOrderRequest, ClosePositionRequest
from routers.etoro.proxy import guard_real

router = APIRouter(prefix="/etoro", tags=["etoro:core"])


@router.get("/search")
def search(symbol: str, client: EtoroClient = Depends(get_etoro_client)):
    """Search by symbol/text and enrich the matching instrument ids with names."""
    res = client.request("GET", "/api/v1/market-data/search",
                         params={"searchText": symbol, "fields": "instrumentId"})
    items = res.get("items", []) if isinstance(res, dict) else []
    ids = [str(i["instrumentId"]) for i in items if i.get("instrumentId") is not None]
    if not ids:
        return {"items": []}
    meta = client.request("GET", "/api/v1/market-data/instruments",
                          params={"instrumentIds": ",".join(ids)})
    rows = meta.get("instrumentDisplayDatas", []) if isinstance(meta, dict) else []
    return {"items": [{
        "instrumentId": r.get("instrumentID"),
        "name": r.get("instrumentDisplayName"),
        "typeId": r.get("instrumentTypeID"),
        "exchangeId": r.get("exchangeID"),
    } for r in rows]}


@router.get("/instruments")
def instruments(ids: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/api/v1/market-data/instruments",
                          params={"instrumentIds": ids})


@router.get("/rates")
def rates(ids: str, client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", "/api/v1/market-data/instruments/rates",
                          params={"instrumentIds": ids})


@router.get("/candles/{instrument_id}")
def candles(instrument_id: int, interval: str = "OneDay", count: int = 50,
            direction: str = "desc", client: EtoroClient = Depends(get_etoro_client)):
    return client.request(
        "GET",
        f"/api/v1/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{count}")


@router.post("/orders")
def create_order(body: UnifiedOrderRequest, account: str = Query("demo"),
                 client: EtoroClient = Depends(get_etoro_client)):
    if account != "demo":
        guard_real()
    seg = "demo/" if account == "demo" else ""
    return client.request("POST", f"/api/v2/trading/execution/{seg}orders",
                          json=body.model_dump(exclude_none=True))


@router.post("/close/{position_id}")
def close_position(position_id: int, body: ClosePositionRequest,
                   account: str = Query("demo"),
                   client: EtoroClient = Depends(get_etoro_client)):
    if account != "demo":
        guard_real()
    seg = "demo/" if account == "demo" else ""
    return client.request(
        "POST",
        f"/api/v1/trading/execution/{seg}market-close-orders/positions/{position_id}",
        json=body.model_dump(exclude_none=True))


@router.get("/portfolio")
def portfolio(account: str = Query("demo"), client: EtoroClient = Depends(get_etoro_client)):
    path = ("/api/v1/trading/info/demo/portfolio" if account == "demo"
            else "/api/v1/trading/info/portfolio")
    return client.request("GET", path)


@router.get("/pnl")
def pnl(account: str = Query("demo"), client: EtoroClient = Depends(get_etoro_client)):
    return client.request("GET", f"/api/v1/trading/info/{account}/pnl")


@router.get("/history")
def history(account: str = Query("demo"), minDate: Optional[str] = None,
            page: Optional[int] = None, pageSize: Optional[int] = None,
            client: EtoroClient = Depends(get_etoro_client)):
    path = ("/api/v1/trading/info/trade/demo/history" if account == "demo"
            else "/api/v1/trading/info/trade/history")
    return client.request("GET", path, params=drop_none({
        "minDate": minDate, "page": page, "pageSize": pageSize}))
```

- [ ] **Step 4: Add core to the aggregator (final state)**

Replace `back/routers/etoro/__init__.py` with:

```python
"""Aggregate eToro sub-routers into a single router mounted under /etoro."""
from fastapi import APIRouter

from routers.etoro import settings, core, proxy

router = APIRouter()
router.include_router(settings.router)
router.include_router(core.router)
router.include_router(proxy.router)
```

- [ ] **Step 5: Update `back/tests/test_etoro_wiring.py` to the final state**

Replace its contents with:

```python
def test_aggregated_router_exposes_settings_core_and_proxy():
    from routers.etoro import router
    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/etoro/credentials" in paths          # settings
    assert "/etoro/search" in paths               # core
    assert "/etoro/orders" in paths               # core
    assert "/etoro/api/{version}/{path}" in paths  # proxy catch-all
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_etoro_core.py tests/test_etoro_wiring.py -v`
Expected: PASS (core 5 tests + wiring 1).

- [ ] **Step 7: Commit**

```bash
git add back/routers/etoro/core.py back/routers/etoro/__init__.py \
        back/tests/test_etoro_core.py back/tests/test_etoro_wiring.py
git commit -m "feat(quantiq): typed core endpoints (search-enrich, orders v2, close, portfolio, pnl)"
```

---

### Task 5: Full suite + live smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the whole back/ offline suite**

Run: `python -m pytest tests/ -q`
Expected: all PASS — existing back tests + supabase_client, vault, client, deps, settings, models, proxy, core, wiring. No references to the deleted routers remain.

- [ ] **Step 2: Confirm the app boots with the new routes**

Run: `python -c "import main; paths=[getattr(r,'path','') for r in main.app.routes]; print('proxy' , '/etoro/api/{version}/{path}' in paths); print('search', '/etoro/search' in paths)"`
Expected: prints `proxy True` and `search True`.

- [ ] **Step 3: Live smoke (needs Supabase running + network; skip if offline)**

Start the API: `python -m uvicorn main:app --port 8799 --log-level warning` (background), then:

```bash
# typed search now returns NAMES
curl -s -H "X-User-Id: 11111111-1111-1111-1111-111111111111" "http://127.0.0.1:8799/etoro/search?symbol=BTC"
# proxy reaches the official agent-portfolios path (was broken before)
curl -s -H "X-User-Id: 11111111-1111-1111-1111-111111111111" "http://127.0.0.1:8799/etoro/api/v1/agent-portfolios"
# demo portfolio via typed core
curl -s -H "X-User-Id: 11111111-1111-1111-1111-111111111111" "http://127.0.0.1:8799/etoro/portfolio?account=demo"
```
Expected: search returns items with `name` fields (e.g. Bitcoin); agent-portfolios returns 200 JSON (not 404); portfolio returns the demo account JSON. Stop the server when done (TaskStop / Ctrl+C).

- [ ] **Step 4: Commit (only if any tweak was needed)**

```bash
git add -A
git commit -m "chore(quantiq): verify eToro proxy + typed core end-to-end"
```

---

## Self-Review notes

- **Spec coverage:** client host base (Task 2), models (Task 1), proxy + guard (Task 3), typed core search-enrich/candles/rates/orders v2/close/portfolio/pnl/history (Task 4), delete drifted routers + tests (Task 2), reference json committed (Task 2), aggregator/wiring (Tasks 2–4), verification + live smoke (Task 5). ✓
- **Type/name consistency:** `EtoroClient.request(method, full_path, *, params, json)` and `BASE_URL = "https://public-api.etoro.com"` used identically in proxy + core + client test; `UnifiedOrderRequest`/`ClosePositionRequest` from `etoro_api.models` used in core + tests with `model_dump(exclude_none=True)`; `guard_real` defined in `proxy.py` and imported by `core.py`; `get_etoro_client` overridden in every router test. ✓
- **Placeholders:** none — every code step is complete.
- **Green-at-every-step:** Task 2 deletes the old routers and their tests in the same commit that changes the client base, so no task leaves a broken/failing suite.
```
