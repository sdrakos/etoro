# Design: Screener category browse (all eToro categories, separately)

**Ημερομηνία:** 2026-06-04
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Επεκτείνει το screener (`back/routers/screener.py`) με browse ανά κατηγορία, χρησιμοποιώντας το eToro instrument catalog που ήδη χτίστηκε (15309 instruments με `asset_class`/`current_rate`/`exchange`). Δεν αλλάζει το `/screener/{universe}` ή το `/movers`.

## Γιατί

Το eToro screener (screenshot p4) έχει tabs ανά κατηγορία: **Stocks, Crypto, ETF, Indices, Commodities, Currencies**. Το υπάρχον `/screener/{universe}` είναι μόνο US-stock universes (sp500/nasdaq100). Ο χρήστης θέλει **όλες τις κατηγορίες, η καθεμία ξεχωριστά** — browse όλο τον eToro κατάλογο ανά asset class με live τιμές. Bonus: σύμβολα όπως T/CVX/ABT (που στο eToro είναι crypto) εμφανίζονται **σωστά** στην κατηγορία Crypto αντί για null.

## Αποφάσεις (κλειδωμένες)

- **Όλες οι 6 κατηγορίες**, η καθεμία ξεχωριστή browsable λίστα μέσω ενός parameterized endpoint.
- **Paginated + sort + search.**
- Keys: `.env` demo (server-side), όπως ο υπόλοιπος screener.
- Reuse: catalog (`asset_class`/`current_rate`), `/closing-price` (change%), `/rates` (live bid/ask best-effort).

## Μη-στόχοι (YAGNI)

- Όχι αλλαγή στο `/screener/{universe}` ή `/movers`.
- Όχι νέα δεδομένα από eToro πέρα από όσα ήδη τραβάμε.
- Όχι frontend (το backend είναι additive· UI tabs σε επόμενο frontend spec).

---

## Αρχιτεκτονική

```
back/
  data_cache/etoro_catalog.py   # + query(asset_class, q, sort, page, page_size) + index
  routers/screener.py           # + GET /screener/category/{category}
```

### Category → asset_class mapping

```python
_CATEGORY_MAP = {
    "stocks": "Stocks", "crypto": "Crypto", "etf": "ETF",
    "indices": "Indices", "commodities": "Commodity", "currencies": "Forex",
}
```
Άγνωστη category → `HTTPException(404)`.

### `EtoroCatalog.query(...)`

```python
def query(self, asset_class: str, q: str | None = None,
          sort: str = "name", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """Return (rows, total) for one asset_class, optionally text-filtered, sorted, paginated."""
```
- Φίλτρο: `WHERE asset_class = ?` (+ `AND (symbol LIKE ? OR display_name LIKE ?)` όταν `q`, case-insensitive `%q%`).
- `total` = COUNT πριν το LIMIT.
- DB-level sort μόνο για `name` (display_name) και `symbol`· για `change`/`price` η ταξινόμηση γίνεται στο endpoint (χρειάζεται live data) — βλ. παρακάτω.
- LIMIT/OFFSET για pagination.
- Νέο index: `CREATE INDEX idx_instruments_asset ON instruments(asset_class)`.

### Endpoint `GET /screener/category/{category}`

Query params: `page=1`, `pageSize=50` (max 200), `sort=change` (∈ `change|name|price`), `dir=desc`, `q=None`.

Flow:
1. `asset_class = _CATEGORY_MAP[category]` (404 αν άγνωστη).
2. **sort by name** → `catalog.query(asset_class, q, sort="name", page, page_size)` (DB paginates· φθηνό). Μετά live-enrich μόνο τη σελίδα.
3. **sort by change/price** → φόρτωσε ΟΛΑ τα rows της κατηγορίας (+q) από το catalog (`catalog.query(..., page=1, page_size=10_000)`), enrich με change/price (closing-price bulk + current_rate), sort στη Python, paginate, μετά `/rates` για τη σελίδα. (Crypto ~100, Stocks ~6000 — εντός μνήμης.)
4. **Live enrich** (για τα rows της σελίδας):
   - `/rates` (batched) για live bid/ask → `sell`/`buy`· `price = lastExecution else current_rate`.
   - `/closing-price` (bulk, memoized) → prev close → `change_pct = (price − prevClose)/prevClose*100`· `is_open`.
   - `exchange`, `instrument_id` από catalog· `sentiment_buy_pct = None`.
5. Επιστρέφει wrapper:
```python
class CategoryPage(BaseModel):
    items: list[ScreenerRow]
    total: int
    page: int
    pageSize: int
    category: str
```

### ScreenerRow

Ίδιο με το υπάρχον (ticker=symbol, name=display_name, sector=asset_class ή "", price, sell, buy, change_pct, sentiment_buy_pct=None, is_open, exchange, instrument_id, volume=None, market_cap/pe=None). Για το category browse, `ticker=symbol`, `name=display_name`, `sector=asset_class`.

## Data flow (crypto tab, sort by change)

```
GET /screener/category/crypto?sort=change&dir=desc&page=1&pageSize=50
  → catalog.query("Crypto", all) → ~100 instruments (id, symbol, name, current_rate, exchange)
  → /closing-price (bulk, memoized) → prev close → compute change% per row
  → sort by change desc → page 1 (50)
  → /rates(page ids) → live bid/ask → price/sell/buy
  → {items:[...], total:~100, page:1, pageSize:50, category:"crypto"}
```

## Error handling

- Άγνωστη category → 404.
- pageSize > 200 → clamp στο 200· page < 1 → 1.
- Λείπουν `.env` keys → 503 (από `get_server_client`). Network → 502.
- Άδειο catalog → `{items:[], total:0,...}` (καλεί `POST /screener/refresh-etoro-catalog` πρώτα).

## Testing (offline, mocked eToro)

1. **`test_etoro_catalog.py`** (+tests) — `query`: filter by asset_class, `q` text filter, name sort, pagination (total + page slice).
2. **`test_screener_category.py`** (new) — με FakeEtoro (catalog από discover + closing + rates):
   - mapping category→asset_class· 404 σε άγνωστη.
   - sort=name paginates· sort=change ταξινομεί by computed change.
   - wrapper `{items,total,page,pageSize,category}`· q filter· pageSize clamp 200.
   - crypto-collision symbol (π.χ. ABT crypto) εμφανίζεται στο category=crypto με σωστά δεδομένα.

## Dependencies

Καμία νέα.

## Επιπτώσεις

- Το frontend θα δείξει tabs ανά κατηγορία (επόμενο spec)· το backend additive.
- Reuse του catalog/closing/rates· το `current_rate` ως price source (αξιόπιστο για όλες τις κατηγορίες).
- Live verify: `GET /screener/category/crypto?sort=change` → top crypto movers· `category/stocks?q=apple` → Apple.
