# Design: QUANTIQ — Supabase foundation + eToro API router

**Ημερομηνία:** 2026-06-03
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σειρά:** 1ο spec του QUANTIQ (από 6 υπο-έργα)

## Πλαίσιο: το QUANTIQ συνολικά

Το QUANTIQ είναι multitenant πλατφόρμα για automatic trading στο eToro: έτοιμες
στρατηγικές με backtest (γραφήματα + quant metrics), σχεδίαση στρατηγικών με prompt
μέσα από την εφαρμογή, και live trading. Σπάει σε υπο-έργα — καθένα δικό του
spec → plan → υλοποίηση:

1. **Supabase foundation + eToro API router** ← *αυτό το spec*
2. eToro ως `trader/` data source (real eToro τιμές για backtest)
3. Backtest results με charts + quant metrics (UI-ready)
4. Prompt-to-strategy designer (LLM → strategy → backtest)
5. Live auto-trading executor (strategy → eToro orders ανά tenant)
6. Multitenant platform (πραγματικό Auth, settings UI, frontend)

## Στόχος αυτού του spec

Στήσιμο του Supabase backend **τοπικά πρώτα** (με σύνδεση σε cloud/real αργότερα,
χωρίς αλλαγές κώδικα) και ένα FastAPI router που εκθέτει **όλα** τα eToro Public API
endpoints, με τα κλειδιά κάθε χρήστη να φυλάσσονται κρυπτογραφημένα σε per-tenant
key vault στο Supabase.

## Αποφάσεις (κλειδωμένες στο brainstorming)

- **1ο deliverable:** Supabase foundation + eToro router μαζί (end-to-end).
- **Tenant identity (τώρα, local):** dev `X-User-Id` header· το FastAPI διαβάζει τα
  κλειδιά με `service_role`. Insecure-by-design για local· αντικαθίσταται από
  Supabase Auth JWT verification πριν πάμε real (μόνο το dependency αλλάζει).
- **Key vault:** app-level **Fernet** encryption (key από `back/.env`). Η ΒΔ δεν
  βλέπει ποτέ plaintext. RLS ορίζεται σωστά από τώρα.
- **Keys που χρησιμοποιούμε:** demo-environment eToro keys (στο `back/.env`), οπότε
  τα execution endpoints δοκιμάζονται ελεύθερα.

## Μη-στόχοι (YAGNI)

- Όχι πραγματικό Auth/login UI (υπο-έργο #6). Χρησιμοποιούμε dev header.
- Όχι frontend/settings σελίδα — μόνο τα API endpoints για credentials.
- Όχι σύνδεση στο cloud Supabase τώρα — μόνο local, με portable config.
- Όχι αλλαγές στο `trader/` ή στους Massive routers.

---

## Αρχιτεκτονική

```
etoro/
├── supabase/                      # local Supabase (CLI)
│   ├── config.toml
│   └── migrations/
│       └── <ts>_etoro_credentials.sql
├── back/
│   ├── .env                       # + SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, QUANTIQ_ENC_KEY
│   ├── supabase_client.py         # supabase-py client (service_role)
│   ├── etoro/                     # eToro integration package
│   │   ├── __init__.py
│   │   ├── client.py              # EtoroClient (httpx wrapper)
│   │   ├── vault.py               # Fernet encrypt + supabase upsert/read
│   │   └── deps.py                # get_etoro_client dependency (+ dev fallback)
│   └── routers/
│       └── etoro/                 # eToro router package (mounted /etoro)
│           ├── __init__.py        # aggregates sub-routers
│           ├── settings.py        # /etoro/credentials
│           ├── market_data.py
│           ├── trading.py
│           ├── social.py
│           └── agent_portfolios.py
```

### Supabase local foundation

- `supabase init` (δημιουργεί `supabase/config.toml`) και `supabase start` (Postgres
  `:54322`, API `:54321`, Studio). Το `supabase start` τυπώνει `API URL`, `service_role
  key` — μπαίνουν στο `back/.env`.
- Migration (μέσω `supabase migration new etoro_credentials`):

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

- Το FastAPI διαβάζει/γράφει με `service_role` (bypass RLS) στο dev. Οι policies
  υπάρχουν για όταν μπει το πραγματικό JWT auth. Δεν εκθέτουμε τον πίνακα ώστε να μην
  είναι προσβάσιμος από `anon` (no grants).

### Key vault — `back/etoro/vault.py`

- `_fernet()` → `Fernet(QUANTIQ_ENC_KEY)` (key από `back/.env`).
- `set_credentials(user_id, public_key, user_key, environment="demo")` → encrypt και
  τα δύο, upsert στο `etoro_credentials` μέσω supabase-py (service_role).
- `get_credentials(user_id) -> Credentials | None` → fetch row, decrypt, επιστρέφει
  `(public_key, user_key, environment)`.
- `delete_credentials(user_id)` και `has_credentials(user_id)`.

### eToro client — `back/etoro/client.py`

- `EtoroClient(public_key, user_key, *, environment="demo")`.
- `BASE_URL = "https://public-api.etoro.com/api/v1"`.
- `request(method, path, *, params=None, json=None) -> dict` με `httpx.Client`:
  headers `x-api-key`, `x-user-key`, fresh `x-request-id = uuid4()`, browser
  `User-Agent` (Cloudflare απαιτεί — αλλιώς `403 error code 1010`), `Accept:
  application/json`. Επιστρέφει το parsed JSON· σε HTTP error επιστρέφει το eToro
  error body με σωστό status (μέσω FastAPI `HTTPException`).

### Tenant dependency — `back/etoro/deps.py`

- `get_etoro_client(x_user_id: str = Header(..., alias="X-User-Id")) -> EtoroClient`:
  1. `creds = vault.get_credentials(x_user_id)`.
  2. Αν κενό → **dev fallback**: `ETORO_PUBLIC_KEY`/`ETORO_PRIVATE_KEY` από `back/.env`.
  3. Αν ούτε αυτά → `HTTPException(400, "no eToro credentials for user")`.
- Σχόλιο στον κώδικα: αυτό αντικαθίσταται με Supabase JWT verification στο υπο-έργο #6·
  η υπόλοιπη στοίβα δεν αλλάζει.

### Router — `back/routers/etoro/`

Όλα τα sub-routers με `APIRouter`, mounted στο `main.py` (`app.include_router(...)`),
κάτω από prefix `/etoro`. Κάθε endpoint κάνει `client = Depends(get_etoro_client)` και
passthrough στο eToro, επιστρέφοντας το JSON. Πλήρης κάλυψη του eToro Public API:

- **`settings.py`** (`/etoro/credentials`) — δεν χτυπάει eToro, γράφει στο vault:
  - `POST /etoro/credentials` body `{public_key, user_key, environment}` → `set_credentials`.
  - `GET /etoro/credentials` → masked status `{has_keys, environment, public_key_last4}`.
  - `DELETE /etoro/credentials` → `delete_credentials`.
- **`market_data.py`** — `GET /etoro/market-data/search`, `/instruments`,
  `/instruments/rates`, `/instruments/history/closing-price`,
  `/instruments/{instrumentId}/history/candles/{direction}/{interval}/{candlesCount}`,
  `/exchanges`, `/instrument-types`, `/stocks-industries`.
- **`trading.py`** —
  - Execution (demo + real): `POST .../market-open-orders/by-amount`, `.../by-units`,
    `DELETE .../market-open-orders/{orderId}`,
    `POST .../market-close-orders/positions/{positionId}`,
    `DELETE .../market-close-orders/{orderId}`, limit orders POST/DELETE.
  - Info: `GET /etoro/trading/info/{demo|real}/pnl`, `.../portfolio`,
    `.../trade/history`.
- **`social.py`** — feeds (`GET /etoro/feeds/instrument/{marketId}`,
  `/feeds/user/{userId}`, `POST /etoro/feeds/post`), watchlists (πλήρες CRUD + items +
  default + public), `GET /etoro/curated-lists`,
  `GET /etoro/market-recommendations/{itemsCount}`, `GET /etoro/pi-data/copiers`,
  user-info (`/etoro/user-info/people`, `/search`, gain/daily-gain/portfolio/tradeinfo).
- **`agent_portfolios.py`** — `GET/POST /etoro/sub-portfolios`,
  `DELETE /etoro/sub-portfolios/{id}`, user-tokens POST/PATCH/DELETE.

**Safety guard:** τα **real-money** execution endpoints (paths χωρίς `/demo/`) μπαίνουν
αλλά πίσω από flag `QUANTIQ_ALLOW_REAL_EXECUTION` (default `false` → `403`). Όλες οι
δυνατότητες παρόντες, χωρίς ατύχημα. (Τα τρέχοντα keys είναι demo ούτως ή άλλως.)

## Data flow (παράδειγμα: place demo order)

```
caller → POST /etoro/trading/execution/demo/market-open-orders/by-amount
         header X-User-Id: <uuid>, body {InstrumentID, IsBuy, Leverage, Amount}
  → deps.get_etoro_client: vault.get_credentials(uuid) → decrypt → EtoroClient
  → client.request("POST", "/trading/execution/demo/market-open-orders/by-amount", json=body)
  → eToro (x-api-key/x-user-key/x-request-id/UA) → JSON → caller
```

## Error handling

- eToro HTTP errors → επιστρέφονται αυτούσια με το status code (FastAPI `HTTPException`).
- Λείπει `X-User-Id` → 422 (FastAPI Header required).
- Λείπουν credentials & dev fallback → 400 με σαφές μήνυμα.
- Real execution ενώ flag off → 403.
- Cloudflare/network → 502 με σύντομο μήνυμα.

## Testing (offline)

1. **`test_vault.py`** — Fernet encrypt→decrypt round-trip· `set/get` με **mocked**
   supabase-py client (επαληθεύει ότι αποθηκεύεται ciphertext, όχι plaintext).
2. **`test_etoro_client.py`** — `EtoroClient.request` με **mocked** `httpx`: σωστά
   headers (UA present, `x-request-id` UUID, keys), σωστό URL/body, JSON parsing,
   error→HTTPException.
3. **`test_etoro_router.py`** — FastAPI `TestClient` με dependency override
   (`get_etoro_client` → fake client): passthrough για ένα δείγμα ανά sub-router·
   `settings` endpoints με mocked vault· real-execution guard (403 όταν flag off).
4. **Integration smoke (manual):** `supabase start`, εφαρμογή migration, `POST
   /etoro/credentials`, μετά `GET /etoro/market-data/search` → 200.

## Dependencies (`back/requirements.txt`, pinned)

- `supabase` (supabase-py)
- `cryptography` (Fernet)
- `httpx`

## Επιπτώσεις / σημεία προσοχής

- Το `back/config.py` **δεν** αλλάζει· το Supabase wiring μπαίνει σε νέο
  `back/supabase_client.py` ώστε ο Massive client να μένει ανέγγιχτος.
- Το `back/.env` αποκτά `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `QUANTIQ_ENC_KEY`
  (όλα local/dev τιμές). Παραμένει gitignored· ενημερώνουμε `back/.env.example`.
- Σύνδεση σε cloud Supabase αργότερα = αλλαγή μόνο των `SUPABASE_*` τιμών + `supabase
  link` + push migrations. Καμία αλλαγή κώδικα.
- Πέρασμα σε πραγματικό multitenant auth = αντικατάσταση του `get_etoro_client`
  dependency με JWT verification· το vault/client/routers μένουν ίδια.
