# Design: eToro router v2 — generic proxy + typed core

**Ημερομηνία:** 2026-06-03
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Αναθεωρεί το eToro router του spec #1 (`2026-06-03-quantiq-etoro-router-supabase-design.md`). Ο πυρήνας Supabase/vault/settings/deps μένει ίδιος.

## Γιατί

Ο αρχικός router γράφτηκε από το bullaware SKILL.md και **απέκλινε από το επίσημο eToro API**. Σύγκριση με το authoritative `openapi.json` (68 paths, v1+v2) έδειξε:

- **Trade execution** μετακινήθηκε σε ενιαίο **v2** endpoint (`POST /api/v2/trading/execution/{demo/}orders`, schema `UnifiedOrderRequest`). Ο client μας ήταν hardcoded σε `/api/v1` → δεν έφτανε καν το v2.
- **agent-portfolios**: το πραγματικό path είναι `/api/v1/agent-portfolios` (όχι `/sub-portfolios`)· πεδίο `agentPortfolioName` (όχι `subPortfolioName`). Ο router μας έδειχνε σε λάθος path → 404.
- POST bodies ήταν untyped `dict` → δύσχρηστο Swagger.
- Λείπουν endpoints (`/me`, asset-explorer, notifications, comments, order-info, demo trade history κ.ά.).

Το eToro API είναι μεγάλο, versioned και εξελισσόμενο· χειρόγραφος καθρέφτης 68 endpoints είναι treadmill που ήδη παλιώσε. Λύση: **generic proxy** (πάντα συγχρονισμένο) + **λίγα typed convenience endpoints** για τα core actions.

## Αποφάσεις (κλειδωμένες)

- **Generic proxy** καλύπτει όλα τα eToro endpoints (v1 & v2)· κρατάμε λίγα typed «μεγάλα κουμπιά».
- **Αντικατάσταση** των broad explicit routers (market_data, trading-v1, social, agent_portfolios) — τα καλύπτει ο proxy. Κρατάμε `settings.py`.
- **Client**: base = host· οι κλήσεις περνούν πλήρες `/api/v1/…` ή `/api/v2/…`.
- **Real-execution guard**: path-based στο proxy (execution path χωρίς `/demo/`).
- **Typed core**: search(+enrich), candles, rates, create-order(v2), close-position, portfolio, pnl, history.

## Μη-στόχοι (YAGNI)

- Δεν γράφουμε typed model για κάθε eToro endpoint — μόνο για τα core (orders, close).
- Δεν αγγίζουμε Supabase/vault/deps/settings.
- Δεν υλοποιούμε WebSocket/notifications/comments typed — προσβάσιμα μέσω proxy.

---

## Αρχιτεκτονική

```
back/etoro_api/
  client.py            # base = https://public-api.etoro.com ; request(method, full_path, ...)
  models.py            # NEW: UnifiedOrderRequest, ClosePositionRequest
  vault.py, deps.py    # unchanged
  reference/etoro-openapi.json  # NEW: το επίσημο spec (source of truth)
back/routers/etoro/
  __init__.py          # aggregate: settings + core + proxy
  settings.py          # unchanged (/etoro/credentials)
  core.py              # NEW: typed convenience endpoints
  proxy.py             # NEW: generic passthrough
# DELETED: market_data.py, trading.py, social.py, agent_portfolios.py
#          + tests test_etoro_market_data.py, test_etoro_trading.py,
#            test_etoro_social.py, test_etoro_agent_portfolios.py
```

### Client (`client.py` — αλλαγή)

- `BASE_URL = "https://public-api.etoro.com"` (host μόνο).
- `request(method, path, *, params=None, json=None)` όπου `path` είναι πλήρες, π.χ.
  `/api/v1/market-data/search` ή `/api/v2/trading/execution/demo/orders`.
- Headers ίδιοι (x-api-key, x-user-key, x-request-id UUID, browser User-Agent, Accept).
- Error handling ίδιο (HTTPException με upstream status· 502 σε network error).

### Proxy (`proxy.py` — νέο)

- Route: `api_route("/etoro/api/{version}/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE"])`.
  Δηλαδή «`/etoro` + το αυτούσιο eToro path». Π.χ. `GET /etoro/api/v1/market-data/exchanges`.
- `version` πρέπει να ∈ {`v1`,`v2`}· αλλιώς `HTTPException(404, "unknown API version")`.
- Χτίζει `full = f"/api/{version}/{path}"`.
- **Guard**: αν `_is_real_execution(method, full)` → `_guard_real()` (403 όταν flag off).
  `_is_real_execution` = `"/trading/execution/" in full` AND `"/demo/" not in full` AND
  `method in {POST, PUT, PATCH, DELETE}`.
- Περνάει query params (`dict(request.query_params)`) και — για methods με body — το JSON body
  (`await request.json()` αν υπάρχει body, αλλιώς `None`).
- `return client.request(method, full, params=params, json=body)`.
- `async def` (χρειάζεται το raw `Request`)· καλεί τον sync `client.request` (αποδεκτό για dev).
- Ο `_guard_real` ζει στο `core.py` (ή κοινό helper) και επαναχρησιμοποιείται.

### Typed core (`core.py` — νέο)

Όλα `Depends(get_etoro_client)`. Παράμετρος `account: str = "demo"` (∈ demo/real) όπου ισχύει·
για real execution καλείται ο guard.

- `GET /etoro/search` — query `symbol` (ή `q` για searchText). Καλεί
  `/api/v1/market-data/search` (παίρνει instrumentIds), μετά **enrich**:
  `/api/v1/market-data/instruments?instrumentIds=…` → επιστρέφει list από
  `{instrumentId, name, typeId, exchangeId}`. Λύνει το «search δίνει μόνο id».
- `GET /etoro/instruments` — query `ids` (comma) → metadata passthrough.
- `GET /etoro/candles/{instrument_id}` — query `interval`, `count` (≤1000), `direction` (asc/desc, default desc)
  → `/api/v1/market-data/instruments/{id}/history/candles/{direction}/{interval}/{count}`.
- `GET /etoro/rates` — query `ids` (comma) → `/api/v1/market-data/instruments/rates`.
- `POST /etoro/orders` — body `UnifiedOrderRequest` (typed), query `account` (demo/real).
  → `/api/v2/trading/execution/{('demo/' if demo)}orders`. Real → guard.
- `POST /etoro/close/{position_id}` — body `ClosePositionRequest`, query `account`.
  → `/api/v1/trading/execution/{('demo/' if demo)}market-close-orders/positions/{position_id}`.
  Real → guard.
- `GET /etoro/portfolio` — query `account` → `/api/v1/trading/info/{demo|}portfolio`
  (demo: `/trading/info/demo/portfolio`, real: `/trading/info/portfolio`).
- `GET /etoro/pnl` — query `account` → `/api/v1/trading/info/{demo|real}/pnl`.
- `GET /etoro/history` — query `account`, `minDate`, optional `page`,`pageSize`
  → demo: `/api/v1/trading/info/trade/demo/history`, real: `/api/v1/trading/info/trade/history`.

### Models (`models.py` — νέο)

Από το `openapi.json`:

- `UnifiedOrderRequest` (v2): required `action: str`, `transaction: str`; optional/nullable
  `symbol`, `instrumentId: int`, `settlementType`, `orderType: str`, `triggerRate: float`,
  `leverage: int`, `amount: float`, `orderCurrency`, `units: float`, `contracts: float`,
  `stopLossRate: float`, `takeProfitRate: float`, `stopLossType`, `additionalMargin: float`,
  `positionIds: list`. Pydantic `model_dump(exclude_none=True)` πριν την αποστολή (μην στέλνεις None — eToro convention).
- `ClosePositionRequest`: required `InstrumentID: int`; optional `UnitsToDeduct: float | None`
  (PascalCase — όπως το spec). Στέλνεται ως-έχει.

## Data flow (create demo order)

```
POST /etoro/orders?account=demo  body {action,instrumentId,amount,leverage,...}
  → core.create_order: validate UnifiedOrderRequest
  → client.request("POST", "/api/v2/trading/execution/demo/orders",
                   json=model.model_dump(exclude_none=True))
  → eToro v2 → JSON → caller
```

## Error handling

- Άγνωστη version στο proxy → 404.
- Real execution & flag off → 403 (proxy & core).
- eToro errors → upstream status (HTTPException), network → 502.
- Λείπει `X-User-Id` / credentials → όπως πριν (422/400 από deps).

## Testing (offline)

1. **`test_etoro_client.py`** (update): base host + full-path· headers ίδια.
2. **`test_etoro_proxy.py`** (new): forward v1 & v2 path· query+body passthrough· version `v3`→404·
   real-exec path POST→403 (flag off) / demo path→pass· flag on→pass.
3. **`test_etoro_core.py`** (new): search-enrich (mock 2 calls)· candles/rates/portfolio/pnl/history σωστά paths·
   create-order → v2 path + `exclude_none` body· close → σωστό path· `account=real` → guard.
4. **`test_etoro_models.py`** (new): UnifiedOrderRequest required action/transaction· exclude_none.
5. **`test_etoro_wiring.py`** (update): aggregator εκθέτει settings + core + proxy representative paths.
6. Διαγραφή των 4 παλιών router test files.

## Files touched (σύνοψη)

| Αρχείο | Αλλαγή |
|---|---|
| `back/etoro_api/client.py` | base host + full-path |
| `back/etoro_api/models.py` | new |
| `back/etoro_api/reference/etoro-openapi.json` | new (reference) |
| `back/routers/etoro/proxy.py` | new |
| `back/routers/etoro/core.py` | new |
| `back/routers/etoro/__init__.py` | aggregate settings+core+proxy |
| `back/routers/etoro/{market_data,trading,social,agent_portfolios}.py` | **delete** |
| `back/tests/test_etoro_{market_data,trading,social,agent_portfolios}.py` | **delete** |
| `back/tests/test_etoro_{proxy,core,models}.py` | new |
| `back/tests/test_etoro_client.py`, `test_etoro_wiring.py` | update |

## Επιπτώσεις

- Το `/docs` δείχνει: settings + ~8 typed core endpoints (καθαρά) + το proxy catch-all. Πολύ πιο
  ευανάγνωστο από τα ~50 παλιά.
- Καμία αλλαγή σε Supabase/vault/deps/settings — ο πυρήνας #1 μένει.
- Μελλοντικά: αν θελήσουμε πλήρη typed κάλυψη, codegen από το `reference/etoro-openapi.json`.
- Το eToro live smoke (search/portfolio) που πέρασε στο #1 παραμένει — απλώς μέσω νέων paths.
