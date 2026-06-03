# Design: Screener με live eToro τιμές + Daily Movers

**Ημερομηνία:** 2026-06-03
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Αλλάζει την πηγή τιμών του υπάρχοντος `back/routers/screener.py` από Massive (end-of-day) σε eToro (live). Πρώτο βήμα προς το eToro-style frontend (watchlist/portfolio/movers/charts = επόμενα specs).

## Γιατί

Ο screener σήμερα δείχνει **Massive grouped-daily close** (καθυστερημένες exchange τιμές, όχι eToro). Ο χρήστης θέλει να δείχνει τα ίδια με το eToro web app (screenshots p4/p6): **Change %, Sell (bid), Buy (ask), Sentiment (% buying), Exchange**, και **Daily Movers** (p8). Το eToro API τα δίνει όλα: `/rates` (live bid/ask), `/instruments/discover` (`dailyPriceChange`, `buyHoldingPct`, `exchangeID`, `symbol`).

## Αποφάσεις (κλειδωμένες)

- **Keys:** ο screener χρησιμοποιεί τα `.env` demo eToro keys (server-side, market-data — όχι X-User-Id). Μένει public.
- **Mapping:** eToro instrument catalog cache (paging `/instruments/discover`), όχι 500 per-symbol κλήσεις.
- **Live price:** `/rates` (bid/ask/lastExecution), batched + memoized.
- **Change/Sentiment/Exchange:** από το catalog (`dailyPriceChange`/`buyHoldingPct`/exchange), refreshed περιοδικά.
- **Volume:** null (το eToro `/rates` δεν το δίνει). `market_cap`/`pe_ratio`: αμετάβλητα (best-effort Massive metadata cache).
- **52W range & sparkline:** εκτός scope (v2 — θέλουν candles).

## Μη-στόχοι (YAGNI)

- Όχι frontend αλλαγές (το backend είναι additive· το React app θα δείξει τις νέες στήλες αργότερα).
- Όχι watchlist/portfolio/charts/home views (ξεχωριστά specs).
- Όχι αλλαγές σε vault/trading/proxy/core.

---

## Αρχιτεκτονική

```
back/
  etoro_api/
    server.py          # NEW: get_server_client() — EtoroClient από .env (no tenant)
  data_cache/
    etoro_catalog.py   # NEW: EtoroCatalog SQLite (symbol→id + change/sentiment/exchange)
  routers/
    screener.py        # MODIFIED: price source = eToro· + /screener/movers + /refresh-etoro-catalog
```

### Server-side eToro client (`etoro_api/server.py`)

```python
def get_server_client() -> EtoroClient:
    """EtoroClient από τα .env ETORO_* keys (για shared market-data, no tenant)."""
```
- Διαβάζει `ETORO_PUBLIC_KEY`/`ETORO_PRIVATE_KEY` από `back/.env` (lazy).
- `HTTPException(503, "eToro keys missing")` αν λείπουν.
- Επαναχρησιμοποιεί το `EtoroClient` (host base, full `/api/vN/...` paths).

### eToro catalog cache (`data_cache/etoro_catalog.py`)

SQLite στο `~/.etoro/etoro_catalog.db`:

```sql
CREATE TABLE IF NOT EXISTS instruments (
    symbol             TEXT PRIMARY KEY,   -- uppercase
    instrument_id      INTEGER NOT NULL,
    exchange_id        INTEGER,
    exchange_name      TEXT,
    display_name       TEXT,
    type_id            INTEGER,
    daily_change       REAL,
    sentiment_buy_pct  REAL,
    is_open            INTEGER,
    updated_at         REAL
);
CREATE INDEX IF NOT EXISTS idx_instruments_id ON instruments(instrument_id);
```

Methods:
- `upsert(rows: list[dict])` — upsert by `symbol`.
- `get_many(symbols) -> dict[str, dict]` — case-insensitive lookup.
- `set_exchange_names(mapping: dict[int,str])` — back-fill `exchange_name` by `exchange_id`.
- `count() -> int`.

### Catalog refresh (`screener.refresh_catalog`)

`POST /screener/refresh-etoro-catalog`:
1. `client = get_server_client()`.
2. Page `/api/v1/instruments/discover` με
   `fields=instrumentId,symbol,displayname,exchangeID,dailyPriceChange,buyHoldingPct,isExchangeOpen`,
   `pageSize=1000`, `page=1..N` μέχρι να γυρίσει άδειο. Upsert κάθε σελίδα (symbol uppercased).
3. `client.request("GET", "/api/v1/market-data/exchanges")` → `{exchange_id: name}` → `set_exchange_names`.
4. Επιστρέφει `{"instruments": <count>, "exchanges": <n>}`.

(Refreshed σπάνια· το catalog cached στον δίσκο. Σε σφάλμα δικτύου → 502.)

### Screener (`GET /screener/{universe}` — αλλαγή πηγής)

`ScreenerRow` (additive — κρατάμε τα παλιά πεδία για backward-compat):
```python
class ScreenerRow(BaseModel):
    ticker: str
    name: str
    sector: str
    instrument_id: Optional[int] = None
    exchange: Optional[str] = None
    price: Optional[float] = None        # eToro lastExecution
    sell: Optional[float] = None         # eToro bid
    buy: Optional[float] = None          # eToro ask
    change_pct: Optional[float] = None   # eToro dailyPriceChange
    sentiment_buy_pct: Optional[float] = None  # eToro buyHoldingPct
    is_open: Optional[bool] = None
    volume: Optional[float] = None       # null (eToro rates lacks it)
    market_cap: Optional[float] = None   # best-effort (Massive metadata cache)
    pe_ratio: Optional[float] = None     # best-effort
```

Flow:
1. `tickers = _load_universe(universe)` (αμετάβλητο: sp500/nasdaq100/combined από τα JSON).
2. `catalog = EtoroCatalog(...)`; `mapped = catalog.get_many([t["ticker"] for t in tickers])`.
3. instrumentIds = όσα mapped· **bulk `/rates`** σε batches (π.χ. 100 ids/κλήση, repeated params):
   `client.request("GET", "/api/v1/market-data/instruments/rates", params={"instrumentIds": batch_ids})`
   → map `instrumentID → {bid, ask, lastExecution}`. Memoized 10s (όπως τώρα).
4. Για κάθε ticker: row με `price=lastExecution`, `sell=bid`, `buy=ask`, `change_pct=daily_change`,
   `sentiment_buy_pct`, `exchange=exchange_name`, `is_open` από το catalog· `market_cap/pe` από το
   metadata cache. Unmapped tickers → τιμές null (μέχρι refresh).
5. Επιστρέφει `list[ScreenerRow]`.

Το παλιό `_get_two_recent_days` (Massive grouped-daily) **αφαιρείται** (δεν χρειάζεται για τιμή).
Το `_refresh_metadata` / metadata cache (market_cap/pe) **μένει** ως-έχει.

### Daily Movers (`GET /screener/movers`)

`GET /screener/movers?universe=combined&direction=gainers&limit=20`:
- Παίρνει τα screener rows (ίδια λογική), φιλτράρει όσα έχουν `change_pct is not None`,
  ταξινομεί φθίνουσα (gainers) ή αύξουσα (losers), επιστρέφει top `limit`.
- `direction ∈ {gainers, losers}` (default gainers)· `limit` default 20.

## Data flow (παράδειγμα)

```
GET /screener/sp500
  → universe tickers (JSON)
  → catalog.get_many(tickers) → instrumentIds + change%/sentiment/exchange
  → /rates (batched) → live bid/ask/lastExecution
  → ScreenerRow[]  (price=lastExecution, sell=bid, buy=ask, change=dailyPriceChange, sentiment=buyHoldingPct)
```

## Error handling

- Λείπουν `.env` eToro keys → 503 (από `get_server_client`).
- eToro network/HTTP error → 502 (από `EtoroClient`).
- Άδειο catalog (δεν έχει γίνει refresh) → rows με null τιμές + (προαιρετικά) header/note· ο χρήστης
  καλεί `POST /screener/refresh-etoro-catalog`.
- Unknown universe → 404 (αμετάβλητο).

## Testing (offline)

1. **`test_etoro_catalog.py`** — upsert/get_many (case-insensitive), set_exchange_names.
2. **`test_screener_etoro.py`** (αντικαθιστά/επεκτείνει το υπάρχον) — με mocked `get_server_client`
   (fake EtoroClient: discover pages, rates, exchanges) + temp catalog:
   - catalog refresh γεμίζει instruments + exchange names.
   - `GET /screener/{u}`: price=lastExecution, sell=bid, buy=ask, change=dailyPriceChange,
     sentiment=buyHoldingPct, exchange σωστό· unmapped ticker → null.
   - rates batching (π.χ. 250 ids → 3 κλήσεις των 100).
   - `GET /screener/movers`: σωστή ταξινόμηση/limit για gainers & losers.
3. Όλα offline (κανένα δίκτυο). Τα Massive metadata tests μένουν.

## Dependencies

Καμία νέα (httpx/pydantic/sqlite ήδη υπάρχουν).

## Επιπτώσεις

- Το React frontend δεν σπάει (πεδία additive)· θα δείξει τις νέες στήλες (sell/buy/sentiment/exchange)
  σε επόμενο frontend spec.
- Ο screener γίνεται eToro-first· market_cap/pe παραμένουν best-effort (Massive Basic).
- Το catalog (symbol→instrumentId + exchange) είναι **επαναχρησιμοποιήσιμο** από watchlist/movers/#2
  data source αργότερα.
- Live verification: `POST /screener/refresh-etoro-catalog` μετά `GET /screener/sp500` → live eToro τιμές·
  `GET /screener/movers` → biggest gainers/losers.
