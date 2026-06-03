# Design: eToro-style screener frontend + near-live prices

**Ημερομηνία:** 2026-06-04
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Ενώνει το νέο screener backend (category browse + live eToro τιμές) με το React frontend (`front/`). Λύνει το «παγωμένες & λάθος τιμές» και κάνει το UI σαν το eToro (screenshots p4/p6).

## Γιατί

Το frontend δεν άλλαξε: δείχνει **παλιές στήλες** (price/volume/mktcap/pe) και χτυπάει το παλιό `/screener/{universe}`. Οι τιμές **παγώνουν** γιατί (α) το backend δεν ξαναφρεσκάρει ποτέ το catalog (το `current_rate` μένει στο τελευταίο refresh) και (β) δεν δείχνει τις eToro στήλες (sell/buy/change/sentiment/exchange). Ο χρήστης θέλει eToro-style UI με μη-παγωμένες, σωστές τιμές.

## Αποφάσεις (κλειδωμένες)

- **Near-live freshness:** το backend auto-refreshάρει το catalog κάθε ~90s· το frontend κάνει poll. Τιμές ~1-2 λεπτά φρέσκες (όχι tick-real-time).
- **Frontend = category tabs** (Stocks/Crypto/ETF/Indices/Commodities/Currencies), eToro-style στήλες, server-side pagination/sort/search.
- **WebSocket = future** (βλ. «Μελλοντικά»).
- Keys: `.env` demo (server-side, ήδη).

## Μη-στόχοι (YAGNI)

- Όχι WebSocket τώρα (μελλοντικό — true tick real-time).
- Όχι αλλαγή στα backend endpoints πέρα από auto-refresh task + status endpoint.
- Όχι charts/watchlist/portfolio views (ξεχωριστά specs).

---

## A. Backend — auto-refresh (λύνει το «παγωμένο»)

**Background refresh task** (`back/main.py` ή `back/routers/screener.py`):
- Στο FastAPI startup (lifespan), ξεκινά ένα asyncio task που κάθε `CATALOG_REFRESH_S` (default 90) τρέχει `refresh_catalog()` σε threadpool (είναι sync/blocking ~60s) και ενημερώνει `_last_refresh_ts`.
- Error-tolerant: exception σε ένα refresh δεν σταματά το loop (log + continue).
- Πρώτο refresh στο startup (αν το catalog είναι άδειο/παλιό).
- Καθαρό shutdown (cancel του task στο lifespan exit).

**`GET /screener/catalog-status`** → `{instruments: <count>, last_refresh_age_s: <float|null>}` (το UI δείχνει «updated Xs ago»).

Reuse: το υπάρχον `refresh_catalog()`. Μικρή προσθήκη (~50 γραμμές + 1 endpoint).

## B. Frontend — eToro-style (`front/`)

Στοίβα ήδη: React + Vite + TanStack Query + TanStack Table + Tailwind.

### Types (`src/types/screener.ts`)
- `Category = "stocks"|"crypto"|"etf"|"indices"|"commodities"|"currencies"` + `CATEGORIES` labels.
- `ScreenerRow` → νέα πεδία: `instrument_id, exchange, sell, buy, change_pct, sentiment_buy_pct, is_open` (κρατάμε `ticker, name, price`· αφαιρούμε από το table τα volume/market_cap/pe ως στήλες, αλλά μένουν optional στο type για backward-compat).
- `CategoryPage = { items: ScreenerRow[]; total; page; pageSize; category }`.

### API (`src/api/screener.ts`)
- `fetchCategory(category, {page, pageSize, sort, dir, q})` → `GET /screener/category/{category}?…` → `CategoryPage`.
- `fetchCatalogStatus()` → `{instruments, last_refresh_age_s}`.

### Hook (`src/hooks/useCategoryData.ts`, αντικαθιστά useScreenerData)
- `useQuery(["screener", category, page, pageSize, sort, dir, q], …)` με `refetchInterval: 30_000`, `staleTime: 30_000`. (Server-side filter/sort/paginate → το hook απλώς περνά params.)

### Components
- **`CategoryTabs`** (νέο): tabs για τις 6 κατηγορίες (αντικαθιστά `UniverseSelector`).
- **`ScreenerTable`** (αλλαγή στήλες): **Market** (ticker + name + market-open dot), **Change %** (χρωματιστό ↑↓), **Sell** (bid), **Buy** (ask), **Sentiment** (% buying — μικρό bar/badge), **Exchange**. Server-side sort → οι headers στέλνουν `sort`/`dir` (όχι client-side sort).
- **`Pagination`** (νέο): page prev/next + total.
- **`SearchBox`** (υπάρχει): τώρα στέλνει `q` στο server (debounced) αντί για client filter.
- **`App.tsx`**: tabs + search + pagination + sort state· «updated Xs ago» από catalog-status· refresh button → invalidate query.

### Tests
- vitest: `api/screener` (fetchCategory URL/params), `useCategoryData` (params→query), `ScreenerTable` (renders νέες στήλες, change color, sentiment), `CategoryTabs` (switch).
- e2e Playwright (`front/e2e/screener.spec.ts`): happy-path — tab switch + search + pagination (mock backend ή live).

## C. Wiring

- Vite proxy ήδη `"/screener": "http://localhost:8765"` → ο backend dev server **πρέπει** να τρέχει στο **8765** (`cd back && python -m uvicorn main:app --reload --port 8765`).
- Frontend dev: `cd front && npm run dev`.
- Το auto-refresh task ξεκινά με το backend· το catalog γεμίζει μόνο του (δεν χρειάζεται manual POST πια).

## Data flow

```
[backend startup] → asyncio loop: refresh_catalog() κάθε 90s → current_rate φρέσκο
[frontend] tab=Crypto, page=1, sort=change
  → GET /screener/category/crypto?page=1&pageSize=50&sort=change&dir=desc
  → CategoryPage {items, total} → table (Change/Sell/Buy/Sentiment/Exchange)
  → poll κάθε 30s → ενημερωμένες τιμές
```

## Error handling

- Backend down → frontend δείχνει error banner (ήδη υπάρχει).
- Άδειο catalog (πριν το πρώτο refresh) → `{items:[], total:0}`· UI «loading market data…».
- Refresh task error → log + συνεχίζει (το επόμενο cycle ξαναπροσπαθεί).

## Testing

- Backend: unit test για το status endpoint + ότι το refresh task καλεί `refresh_catalog` (mock). Offline.
- Frontend: vitest + Playwright (παραπάνω).

## Μελλοντικά (επόμενο spec) — True real-time με WebSocket

Το eToro Public API έχει **WebSocket** (`api-reference/websocket/*`: authentication, topics, example-code). Σε επόμενη φάση:
- Backend WS proxy/relay που κάνει subscribe σε instrument price topics και σπρώχνει live ticks.
- Frontend WS client → tick-by-tick ενημέρωση των ορατών rows (αντί polling).
- Δίνει **πραγματικό** real-time (όχι ~90s). Μεγαλύτερο build — γίνεται αφού σταθεροποιηθεί το near-live UI.

(Αυτό το spec υλοποιεί το **near-live**· το WebSocket είναι ρητά μελλοντική αναβάθμιση.)

## Επιπτώσεις

- Οι τιμές δεν παγώνουν πια (auto-refresh) και είναι σωστές ανά κατηγορία (collisions λυμένα).
- Το UI μοιάζει με το eToro (p4/p6).
- Reuse όλου του backend που χτίστηκε (category/movers/catalog).
