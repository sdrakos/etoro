# Design: Screener exchange filter (μετοχές ανά χρηματιστήριο)

**Ημερομηνία:** 2026-06-04
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Επεκτείνει το screener category browse (`back/routers/screener.py` + `front/`) με φίλτρο ανά **exchange (χρηματιστήριο)**, χρησιμοποιώντας το `exchange_name` που ήδη υπάρχει στον eToro instrument catalog. Δεν αλλάζει το WS/live-prices, το `/movers`, ή το `/screener/{universe}`.

## Γιατί

Ο χρήστης βλέπει τις μετοχές «χύμα»: η κατηγορία Stocks έχει ~12.000 instruments από 32 διαφορετικά χρηματιστήρια (Nasdaq 3706, NYSE 2341, LSE, Euronext, Tokyo, Hong Kong…) ανακατεμένα. Θέλει να διαλέγει **χρηματιστήριο** ώστε η λίστα να γίνεται διαχειρίσιμη (π.χ. «μόνο Nasdaq»). Το `exchange_name` **υπάρχει ήδη** στον catalog — λείπει μόνο το φίλτρο/endpoint/UI.

(Φίλτρο ανά **κλάδο (sector)** ζητήθηκε επίσης, αλλά ο sector **δεν υπάρχει** στα δεδομένα μας — αναβάλλεται ρητά σε ξεχωριστό spec με δική του enrichment strategy. Βλ. «Μη-στόχοι».)

## Αποφάσεις (κλειδωμένες)

- **Server-side filter**, ίδιο pattern με τα υπάρχοντα category/search/sort/pagination. Client-side δεν δουλεύει (το endpoint paginate-άρει server-side, ο browser βλέπει μόνο 50 rows/σελίδα).
- **Dropdown**, όχι tabs/chips (32 exchanges → dropdown είναι το σωστό). Default «All exchanges».
- Το φίλτρο εφαρμόζεται στο catalog **πριν** το pagination/sort, ώστε `total` και sort-by-change/price να μένουν σωστά.
- Τα exchanges είναι **ανά κατηγορία** (Crypto → «Digital Currency» μόνο· Stocks → 32). Αλλαγή κατηγορίας → reset exchange σε «All».

## Μη-στόχοι (YAGNI)

- Όχι sector/κλάδος (ξεχωριστό spec — θέλει enrichment από πηγή που δεν έχουμε φτηνά).
- Όχι αλλαγή σε WS/live-prices, `/movers`, `/screener/{universe}`, catalog refresh.
- Όχι νέα δεδομένα από eToro — χρησιμοποιούμε το `exchange_name` που ήδη τραβάμε στο discover.

---

## Αρχιτεκτονική

```
back/
  data_cache/etoro_catalog.py   # + exchange φίλτρο σε query()/all_for_category(); + exchanges(); + index
  routers/screener.py           # + param exchange στο /category/{category}; + GET /exchanges/{category}
front/
  src/types/screener.ts         # + ExchangeOption
  src/api/screener.ts           # + fetchExchanges(); fetchCategory δέχεται exchange
  src/hooks/useExchanges.ts      # νέο (TanStack Query)
  src/hooks/useCategoryData.ts   # queryKey + params περιλαμβάνουν exchange
  src/components/ExchangeFilter.tsx  # νέο dropdown
  src/App.tsx                    # state exchange + wiring
```

### Backend — `EtoroCatalog`

Νέα μέθοδος:
```python
def exchanges(self, asset_class: str) -> list[dict]:
    """Distinct exchanges για μία asset_class με πλήθος, sorted by count desc.
    Return: [{"exchange": <name>, "count": <n>}, ...] (παραλείπει NULL/κενά)."""
```
- SQL: `SELECT exchange_name, COUNT(*) n FROM instruments WHERE asset_class=? AND exchange_name IS NOT NULL AND exchange_name<>'' GROUP BY exchange_name ORDER BY n DESC`.

Επέκταση των `query(...)` και `all_for_category(...)` με προαιρετικό `exchange: Optional[str] = None`:
- Όταν δοθεί, προσθήκη `AND exchange_name = ?` στο WHERE (πριν το COUNT/total και πριν το LIMIT/OFFSET).
- `total` μετριέται **μετά** το exchange φίλτρο (σωστό count).

Νέο index: `CREATE INDEX IF NOT EXISTS idx_instruments_exchange ON instruments(exchange_name)`.

### Backend — `routers/screener.py`

**`GET /screener/category/{category}`** — νέο query param:
```python
exchange: Optional[str] = Query(None)
```
- Περνά στο `catalog.query(asset, q, sort, page, page_size, exchange=exchange)` (sort=name path) και `catalog.all_for_category(asset, q, exchange=exchange)` (sort=change/price path).
- Τίποτα άλλο δεν αλλάζει (enrich/rates/closing ίδια).

**Νέο `GET /screener/exchanges/{category}`**:
```python
@router.get("/exchanges/{category}")
def category_exchanges(category: str):
    asset = _CATEGORY_MAP.get(category.lower())
    if asset is None:
        raise HTTPException(404, f"Unknown category: {category}")
    return EtoroCatalog(CATALOG_DB).exchanges(asset)   # [{exchange, count}]
```
Καταχώρηση **πριν** το `/{universe}` route (όπως τα άλλα named routes· το prefix `/screener` + `/exchanges/{category}` δεν συγκρούεται με `/{universe}` αλλά κρατάμε τη σειρά για συνέπεια).

### Frontend

**`types/screener.ts`**:
```typescript
export interface ExchangeOption { exchange: string; count: number; }
```

**`api/screener.ts`**:
- `fetchExchanges(category: Category): Promise<ExchangeOption[]>` → `GET /screener/exchanges/{category}`.
- `CategoryParams` αποκτά `exchange?: string`· το `fetchCategory` προσθέτει `qs.set("exchange", params.exchange)` μόνο όταν υπάρχει (αλλιώς το παραλείπει — σημαίνει «All»).

**`hooks/useExchanges.ts`** (νέο):
```typescript
export function useExchanges(category: Category) {
  return useQuery({
    queryKey: ["screener", "exchanges", category],
    queryFn: () => fetchExchanges(category),
    staleTime: 300_000,
  });
}
```

**`hooks/useCategoryData.ts`**: το `params` (που ήδη περιλαμβάνει page/pageSize/sort/dir/q) αποκτά `exchange`· επειδή το queryKey είναι `["screener","category",category,params]`, αλλαγή exchange → νέο fetch αυτόματα. Καμία άλλη αλλαγή.

**`components/ExchangeFilter.tsx`** (νέο): dropdown (`<select>` styled σαν το sort control). Props `{ value: string|null; options: ExchangeOption[]; onChange: (ex: string|null) => void }`. Πρώτη επιλογή «All exchanges» (value ""→null)· οι υπόλοιπες `«{exchange} ({count})»`. Όταν `options` έχει ≤1 στοιχείο, το dropdown εμφανίζεται disabled (π.χ. Crypto).

**`App.tsx`**:
- Νέο state `const [exchange, setExchange] = useState<string|null>(null)`.
- `const exchanges = useExchanges(category)` → περνά `exchanges.data ?? []` στο `ExchangeFilter`.
- `useCategoryData(category, { page, pageSize, sort, dir, q, exchange: exchange ?? undefined })`.
- `onExchange = (ex) => { setExchange(ex); setPage(1); }`.
- Αλλαγή κατηγορίας (`onCategory`) → `setExchange(null)` (reset σε All) + `setPage(1)`.
- Το `ExchangeFilter` μπαίνει στο toolbar δίπλα στο sort control.

## Data flow

```
tab=Stocks → useExchanges("stocks") → [{Nasdaq,3706},{NYSE,2341},...]  → dropdown
διαλέγει «Nasdaq» → setExchange("Nasdaq"), page=1
  → GET /screener/category/stocks?exchange=Nasdaq&page=1&pageSize=50&sort=change&dir=desc
  → catalog φιλτράρει exchange_name='Nasdaq' (total=3706) → enrich → page → WS ticks (ίδια)
αλλάζει tab → Crypto → setExchange(null); useExchanges("crypto") → [{Digital Currency, ...}] (disabled)
```

## Error handling

- Άγνωστη category στο `/exchanges/{category}` → 404 (ίδιο με category browse).
- Άδειο catalog → `exchanges()` επιστρέφει `[]` → dropdown μόνο με «All».
- `exchange` που δεν υπάρχει (π.χ. stale επιλογή μετά από refresh) → 0 rows, `total=0` → το UI δείχνει empty state (ήδη υπάρχει).
- Backend down → ο υπάρχων error banner.

## Testing (offline, mocked)

1. **`test_etoro_catalog.py`** (+tests): `exchanges(asset_class)` → distinct + counts + sorted desc, παραλείπει NULL/κενά· `query(..., exchange=...)` και `all_for_category(..., exchange=...)` → φιλτράρει σωστά + `total` μετά το φίλτρο.
2. **`test_screener_category.py`** (+tests): `GET /category/stocks?exchange=Nasdaq` → μόνο Nasdaq rows + σωστό total· `GET /exchanges/stocks` → λίστα `[{exchange,count}]`· άγνωστη category → 404.
3. **Frontend** (vitest): `fetchExchanges` URL· `fetchCategory` βάζει `exchange` μόνο όταν υπάρχει· `ExchangeFilter` renders options + «All» + onChange· App: αλλαγή exchange → νέο fetch + reset page· αλλαγή category → reset exchange.

## Dependencies

Καμία νέα.

## Επιπτώσεις

- Οι μετοχές παύουν να είναι «χύμα»: ο χρήστης διαλέγει χρηματιστήριο και η λίστα γίνεται διαχειρίσιμη.
- Reuse όλου του υπάρχοντος server-side pipeline (category/search/sort/pagination/WS) — additive, χαμηλό ρίσκο.
- Ανοίγει τον δρόμο για το sector filter (επόμενο spec) με το ίδιο dropdown pattern.
