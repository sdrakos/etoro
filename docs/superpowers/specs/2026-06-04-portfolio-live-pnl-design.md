# Design: Portfolio view + live P&L (WS Spec 2)

**Ημερομηνία:** 2026-06-04
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Δεύτερο spec της διάσπασης του WebSocket feature (το πρώτο: `2026-06-04-screener-websocket-live-design.md`). Προσθέτει μια **Portfolio view** στο frontend με **live P&L** ανά θέση, ξαναχρησιμοποιώντας το `/ws/prices` price-relay που ήδη χτίστηκε. Περιλαμβάνει και **κλείσιμο θέσης** (demo).

## Γιατί

Ο χρήστης βλέπει live τιμές στον screener αλλά **δεν βλέπει το χαρτοφυλάκιό του**. Θέλει μια οθόνη με τις ανοιχτές θέσεις του (demo account) όπου το **κέρδος/ζημία ενημερώνεται tick-by-tick** από το ίδιο live feed, και να μπορεί να **κλείσει** μια θέση. Το backend έχει ήδη το portfolio (`/api/v1/trading/info/demo/portfolio`) και το market-close· λείπει το normalize + η frontend view + το live P&L overlay.

## Αποφάσεις (κλειδωμένες)

- **P&L υπολογίζεται frontend-side** από τις θέσεις (REST) + τα live ticks του **υπάρχοντος `/ws/prices` relay**. Καθαρό reuse — το relay μένει αμετάβλητο, η portfolio απλώς κάνει subscribe τα δικά της `instrument_id`.
- **Account = demo** (τα τωρινά keys), με `get_server_client()` (app keys), όπως ο screener. Real execution παραμένει πίσω από `guard_real()` (`QUANTIQ_ALLOW_REAL_EXECUTION`). Multitenant per-user (X-User-Id/vault) = μελλοντικό.
- **Νέα top-level nav «Screener | Portfolio»** — ο σημερινός screener γίνεται ένα από δύο views.
- **Close ενεργό** (demo): confirm dialog → market-close → refetch.

## Μη-στόχοι (YAGNI)

- Όχι charts / trade history.
- Όχι άνοιγμα νέων θέσεων (μόνο view + close).
- Όχι multitenant per-user τώρα (server client / demo).
- Καμία αλλαγή στο `/ws/prices` relay, στον `EtoroWsClient`, ή στον screener.

---

## Live P&L formula

Από τη μορφή θέσης (επιβεβαιωμένη live από το demo account):
`clientPortfolio.positions[]: {positionID, instrumentID, openRate, units, isBuy, amount, leverage, ...}`

Ανά θέση, με `price` = το live `last` (αλλιώς το seed `current_rate` του catalog):
```
direction = isBuy ? +1 : -1
pnl_usd   = units * (price - openRate) * direction
pnl_pct   = amount ? (pnl_usd / amount) * 100 : null
```
(Σε quote currency· για USD instruments `openConversionRate≈1`. Αγνοούμε fees/conversion — είναι live ένδειξη, όχι λογιστική ακρίβεια. Επαληθεύτηκε: για leverage 1, `units*openRate ≈ amount`.)

**Aggregate:** `total_invested = Σ amount`, `total_pnl_usd = Σ pnl_usd`, `total_pnl_pct = total_invested ? total_pnl_usd/total_invested*100 : null`.

---

## Αρχιτεκτονική

```
back/
  data_cache/etoro_catalog.py   # + get_by_instrument_ids(ids) -> {id: row}
  routers/portfolio.py          # νέο: GET /portfolio/positions, POST /portfolio/close/{id}
  main.py                       # include portfolio.router
front/
  src/types/portfolio.ts        # Position, PortfolioResponse
  src/api/portfolio.ts          # fetchPortfolio(), closePosition()
  src/hooks/usePortfolio.ts     # REST positions (refetch 30s)
  src/lib/pnl.ts                # positionPnl(), aggregatePnl() (pure, tested)
  src/components/PortfolioTable.tsx   # rows + live overlay + Close
  src/components/PortfolioSummary.tsx # Σ invested / Σ P&L$ / total %
  src/views/PortfolioView.tsx   # σύνθεση (usePortfolio + usePriceStream + close)
  src/components/AppNav.tsx      # top-level «Screener | Portfolio»
  src/App.tsx                   # view state· ο screener μετακινείται σε ScreenerView
```

### Backend — `EtoroCatalog.get_by_instrument_ids`

```python
def get_by_instrument_ids(self, ids: Iterable[int]) -> dict[int, dict]:
    """Map instrument_id -> catalog row (symbol, display_name, exchange_name, current_rate).
    Για enrichment θέσεων. Άγνωστα ids απουσιάζουν από το dict."""
```
- SQL `SELECT * FROM instruments WHERE instrument_id IN (...)`· χρησιμοποιεί το υπάρχον `idx_instruments_id`.

### Backend — `routers/portfolio.py`

```python
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

class Position(BaseModel):
    position_id: int
    instrument_id: int
    symbol: Optional[str] = None
    name: Optional[str] = None
    is_buy: bool
    units: float
    open_rate: float
    amount: float
    leverage: float
    current_rate: Optional[float] = None   # seed από catalog (πριν το πρώτο tick)

class PortfolioResponse(BaseModel):
    positions: list[Position]
    account: str
```

**`GET /portfolio/positions`** (`account="demo"`):
1. `client = get_server_client()` (503 αν λείπουν keys).
2. `data = client.request("GET", "/api/v1/trading/info/{demo|}portfolio")`.
3. `raw = data.get("clientPortfolio", {}).get("positions", [])`.
4. enrich με `EtoroCatalog(CATALOG_DB).get_by_instrument_ids([p["instrumentID"] for p in raw])`.
5. map κάθε raw → `Position` (symbol/name/current_rate από catalog row αν υπάρχει).
6. return `PortfolioResponse(positions=..., account=account)`.

**`POST /portfolio/close/{position_id}`** (body `ClosePositionRequest {InstrumentID, UnitsToDeduct?}`, `account="demo"`):
- `if account != "demo": guard_real()`.
- `seg = "demo/" if account=="demo" else ""`.
- `client.request("POST", f"/api/v1/trading/execution/{seg}market-close-orders/positions/{position_id}", json=body.model_dump(exclude_none=True))`.
- return η eToro απάντηση.

`main.py`: `from routers import portfolio` + `app.include_router(portfolio.router)`.

### Frontend

**`types/portfolio.ts`**: `Position` (όπως πάνω, camel→snake όπως το JSON: `position_id, instrument_id, symbol, name, is_buy, units, open_rate, amount, leverage, current_rate`) + `PortfolioResponse { positions: Position[]; account: string }`.

**`api/portfolio.ts`**:
- `fetchPortfolio(): Promise<PortfolioResponse>` → `GET /portfolio/positions`.
- `closePosition(positionId: number, body: { InstrumentID: number; UnitsToDeduct?: number }): Promise<unknown>` → `POST /portfolio/close/{positionId}` (JSON body, throw on !ok).

**`hooks/usePortfolio.ts`**: `useQuery(["portfolio"], fetchPortfolio, { refetchInterval: 30_000 })`.

**`lib/pnl.ts`** (pure, εύκολα testable):
```typescript
export function positionPnl(p: Position, price: number | null):
  { price: number | null; pnlUsd: number | null; pnlPct: number | null };
export function aggregatePnl(rows: {p: Position; price: number|null}[]):
  { invested: number; pnlUsd: number; pnlPct: number | null };
```
- `price = liveLast ?? p.current_rate ?? null`· `pnlUsd = price==null? null : p.units*(price-p.open_rate)*(p.is_buy?1:-1)`.

**`components/PortfolioTable.tsx`** (`{ rows: Position[]; ticks: Map<number,LiveTick>; onClose: (p: Position)=>void; closingId: number|null }`): στήλες Instrument / Direction / Units / Open / Current / P&L $ / P&L % / Close· overlay live `ticks.get(instrument_id)?.last`· χρωματισμός P&L (πράσινο/κόκκινο)· Close κουμπί (disabled όταν `closingId===position_id`).

**`components/PortfolioSummary.tsx`** (`{ invested; pnlUsd; pnlPct }`): header με Σ invested, Σ live P&L $ (χρωματιστό), total %.

**`views/PortfolioView.tsx`**:
- `const { data } = usePortfolio()`· `const stream = usePriceStream()`.
- effect: `stream.subscribe(positions.map(p=>p.instrument_id))`.
- υπολογισμός per-row + aggregate μέσω `pnl.ts`· render Summary + Table.
- close: confirm (window.confirm ή μικρό modal) → `closePosition(p.position_id, { InstrumentID: p.instrument_id })` → on success `queryClient.invalidateQueries(["portfolio"])`· κράτα `closingId` για pending state· error → μήνυμα.

**`components/AppNav.tsx`**: δύο κουμπιά «Screener | Portfolio» (ίδιο segmented look με τα CategoryTabs).

**`App.tsx`**: `const [view, setView] = useState<"screener"|"portfolio">("screener")`· render `<AppNav .../>` + (view==="screener" ? `<ScreenerView/>` : `<PortfolioView/>`). Ο σημερινός screener κώδικας μετακινείται σε `views/ScreenerView.tsx` (καθαρή εξαγωγή, ίδιο markup) ώστε το `App` να μείνει λεπτό shell.

## Data flow

```
[Portfolio tab] → GET /portfolio/positions → θέσεις (open_rate, units, is_buy, seed current_rate)
  → usePriceStream.subscribe(instrument_ids)  (ίδιο /ws/prices relay)
  → ticks → positionPnl ανά row + aggregatePnl → live table + summary (flash)
[Close] → confirm → POST /portfolio/close/{id} {InstrumentID} → invalidate ["portfolio"] → refetch
```

## Error handling

| Σενάριο | Συμπεριφορά |
|---|---|
| Λείπουν keys | `get_server_client` → 503· η view δείχνει error banner |
| Καμία ανοιχτή θέση | `positions: []` → empty state «No open positions» |
| Θέση χωρίς catalog match | `symbol/name=null`, δείχνει instrument_id· P&L υπολογίζεται από open_rate + tick κανονικά |
| Πριν το πρώτο tick | P&L από seed `current_rate`· αν κι αυτό null → «—» |
| Close αποτυχία (network/eToro) | error μήνυμα, η θέση μένει· `closingId` καθαρίζει |
| Real account + guard off | 403 από `guard_real` → surfaced στο UI |
| Backend down | υπάρχων error banner pattern |

## Testing (offline, mocked)

1. **`test_portfolio.py`** (backend, FakeEtoro/server client): `/portfolio/positions` → normalize (`positionID→position_id`, `isBuy→is_buy`, units/openRate/amount) + catalog enrichment (symbol/name/current_rate)· θέση με άγνωστο instrument → symbol=null· `/portfolio/close/{id}` → καλεί το σωστό demo path με `{InstrumentID}` body· non-demo χωρίς flag → 403.
2. **`test_etoro_catalog.py`** (+test): `get_by_instrument_ids` → map ανά id, άγνωστα απουσιάζουν.
3. **Frontend** (vitest): `pnl.ts` (`positionPnl` buy/sell/leverage, `aggregatePnl`)· `usePortfolio`· `PortfolioTable` (rows + live overlay + Close onClick)· `PortfolioSummary`· `AppNav` switch· `closePosition` API URL+body. MSW handlers για `/portfolio/positions` + `/portfolio/close/:id`.

## Dependencies

Καμία νέα.

## Επιπτώσεις

- Ο χρήστης βλέπει το demo χαρτοφυλάκιό του με P&L που κινείται live (ίδιο feed με τον screener) και μπορεί να κλείσει θέση.
- Reuse του `/ws/prices` relay + `usePriceStream` χωρίς καμία αλλαγή τους — επικυρώνει τον σχεδιασμό του Spec 1.
- Ο διαχωρισμός `App` → `ScreenerView`/`PortfolioView` + `AppNav` ανοίγει τον δρόμο για επόμενες οθόνες (watchlist/charts) με ελάχιστο κόστος.
- Multitenant per-user portfolio (X-User-Id/vault) προστίθεται αργότερα χωρίς να αλλάξει αυτή η δομή.
