# Design: Screener live prices με WebSocket (true real-time)

**Ημερομηνία:** 2026-06-04
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Διαδέχεται το near-live REST screener (`docs/superpowers/specs/2026-06-04-screener-frontend-near-live-design.md`). Αντικαθιστά το 30s polling των τιμών με πραγματικό tick-by-tick feed από το eToro WebSocket. Είναι το **Spec 1** μιας διάσπασης σε δύο: εδώ χτίζεται το **WS price-relay foundation + screener live ticks**· το **Spec 2** (Portfolio view + live P&L) θα ξαναχρησιμοποιήσει το ίδιο relay.

## Γιατί

Το near-live REST δίνει σωστό `price` (current_rate) αλλά **bid/ask «—»** για τα περισσότερα instruments (το public REST `/rates` επιστρέφει live bid/ask μόνο για ένα μικρό υποσύνολο) και **change% αναξιόπιστο** (0.00% ή absurd από buggy prevClose math). Το eToro **site** δείχνει live bid/ask + change γιατί τραβάει το authenticated **WebSocket** feed (`wss://ws.etoro.com/ws`). Αυτό το spec φέρνει το ίδιο feed στον screener: πραγματικά live bid/ask/last + σωστό live change%, χωρίς polling.

## Αποφάσεις (κλειδωμένες)

- **Προσέγγιση A — Backend WS relay + shared upstream + fan-out.** Ο backend κρατά **ένα** authenticated eToro WS connection (app keys) και εκθέτει δικό του `/ws/prices` στους browsers. Απορρίφθηκαν: (B) SSE προς browser — subscription changes θέλουν side-channel, όρια connections/browser· (C) frontend κατευθείαν στο eToro WS — **εκθέτει τα API keys στον browser**, ασύμβατο με multitenant.
- **Ένα κοινό app connection** για market data: οι τιμές αγοράς είναι ίδιες για όλους → 1 upstream connection, fan-out σε όλους τους browsers, σέβεται τα rate limits του eToro. Per-user private feeds (orders/positions) έρχονται σε επόμενη φάση.
- **Ο screener φέρνει τη λίστα με REST** (`fetchCategory` → seed rows + metadata + prevClose + is_open)· το WS οδηγεί **μόνο τις τιμές** (bid/ask/last/change) live πάνω στα seed rows.
- **Live change%** υπολογίζεται στον backend από το prevClose (που ήδη τραβάμε από `/closing-price`) σε κάθε tick — διορθώνει το «—»/garbage change.
- **Κλειστά χρηματιστήρια:** `is_open=false` → γκρι τελίτσα + «Closed» badge, κανένα live tick, μένει η τελευταία (seed) τιμή — χωρίς ψεύτικα updates.

## Μη-στόχοι (YAGNI)

- Όχι Portfolio P&L (Spec 2).
- Όχι per-user private feeds (orders/positions/trade-updates) — μόνο app-level shared market data.
- Όχι charts/history/watchlist.
- Δεν πειράζουμε το category browse / catalog refresh / movers — μένουν ως έχουν· το WS αντικαθιστά μόνο το per-row price polling.

---

## eToro WebSocket πρωτόκολλο (επιβεβαιωμένο από τα docs)

- **URL:** `wss://ws.etoro.com/ws`
- **Authenticate:**
  ```json
  { "id": "<guid>", "operation": "Authenticate", "data": { "userKey": "<x-user-key>", "apiKey": "<x-api-key>" } }
  ```
- **Subscribe:**
  ```json
  { "id": "<guid>", "operation": "Subscribe", "data": { "topics": ["instrument:<instrumentId>"], "snapshot": true } }
  ```
- **Unsubscribe:** ίδιο με `"operation": "Unsubscribe"` (χωρίς snapshot).
- **Incoming tick:**
  ```json
  { "messages": [ { "topic": "instrument:100000", "type": "Trading.Instrument.Rate",
                    "id": "<uuid>", "content": "<stringified JSON>" } ] }
  ```
  Το `content` (JSON-parsed) έχει: `Bid` (float), `Ask` (float), `LastExecution` (float), `Date` (ISO-8601), `PriceRateID` (int), + deprecated margin fields.
- **Reconnect:** exponential backoff (1→2→4…30s cap), persist τελευταία quotes, ξαναστείλε Authenticate + Subscribe στο reconnect.
- **Keys:** `ETORO_PUBLIC_KEY` (apiKey) + `ETORO_PRIVATE_KEY` (userKey) από `back/.env` (server-side, ήδη). Cloudflare θέλει browser-like User-Agent — ίδιος κανόνας με τον REST client.

---

## Αρχιτεκτονική

```
Browser (React)                 Backend (FastAPI)                    eToro
 ScreenerTable                   GET(ws) /ws/prices  (δικό μας)       wss://ws.etoro.com/ws
 + usePriceStream  ⇄ ticks ⇄     PriceRelay (singleton)         ⇄     EtoroWsClient (1 shared)
                    {op:"set"}    • ref-count subscriptions             app keys, snapshot=true
                                  • diff → upstream sub/unsub
                                  • parse content → change% → fan-out
```

```
back/
  etoro_api/ws_client.py     # EtoroWsClient: το ένα upstream connection (connect/auth/sub/unsub/reconnect)
  routers/ws_prices.py       # PriceRelay (ref-count + fan-out) + @app.websocket("/ws/prices")
  main.py                    # lifespan: lazy start του relay στον πρώτο subscriber, καθαρό shutdown
front/
  src/hooks/usePriceStream.ts  # browser WS client: reconnect, Map<id,Tick>, subscribe(ids)
  src/components/ScreenerTable.tsx  # merge live ticks πάνω στα seed rows (flash highlight)
  src/App.tsx                  # subscribe ids της σελίδας· χαλαρώνει το 30s poll
```

### Backend — `EtoroWsClient` (`etoro_api/ws_client.py`)

Μία μονάδα, ένα connection. Public API:

```python
class EtoroWsClient:
    def __init__(self, api_key: str, user_key: str): ...
    async def start(self) -> None:            # connect + Authenticate + receive loop (idempotent)
    async def stop(self) -> None:             # καθαρό close
    async def subscribe(self, ids: set[int]) -> None:    # στέλνει Subscribe(snapshot=true) για νέα ids
    async def unsubscribe(self, ids: set[int]) -> None:  # στέλνει Unsubscribe
    def on_tick(self, cb: Callable[[Tick], None]) -> None:  # register fan-out callback
```

- `library`: `websockets` (async). Πρόσθεση στο `back/requirements`/pyproject.
- **Receive loop:** για κάθε `messages[]` με `type=="Trading.Instrument.Rate"`, parse `topic` → `instrument_id`, `json.loads(content)` → `Tick(instrument_id, bid=Bid, ask=Ask, last=LastExecution, ts=Date)`, κάλεσε τα callbacks. Άγνωστα `type` αγνοούνται.
- **Reconnect:** σε close/error → backoff loop· στο επανασύνδεση ξανα-Authenticate + Subscribe το τρέχον active set (κρατημένο σε `self._active: set[int]`)· κρατά `self._last: dict[int, Tick]` για snapshot σε νέους subscribers.
- **Auth gating:** μην στείλεις Subscribe πριν ληφθεί επιβεβαίωση Authenticate (ή απλό await μικρού delay + έλεγχος ότι το socket είναι open).
- **Heartbeat:** το eToro δεν τεκμηριώνει ping interval· στείλε περιοδικό keepalive ping (π.χ. κάθε 20s) και ανέχσου idle· βασίσου στο reconnect αν πέσει.

### Backend — `PriceRelay` + endpoint (`routers/ws_prices.py`)

```python
class PriceRelay:
    """Ref-counts instrument subscriptions across ALL browser clients,
       οδηγεί ένα EtoroWsClient, κάνει fan-out ticks + live change%."""
    def __init__(self, client: EtoroWsClient, closing_provider): ...
    async def attach(self, browser_ws) -> ClientHandle: ...   # νέος browser
    async def set_ids(self, handle, ids: set[int]) -> None:   # diff vs προηγούμενα του client
    async def detach(self, handle) -> None:                   # browser έφυγε → μείωσε refcounts
```

- **Ref-counting:** `Counter[int]`. `set_ids` υπολογίζει `added/removed` για τον συγκεκριμένο client· `refcount[id]++/--`. Όταν `refcount[id]` 0→1 → `client.subscribe({id})`· όταν 1→0 → **debounced** `unsubscribe` (κράτα ~10s πριν το upstream unsubscribe, ώστε pagination/tab-flip να μην κάνει churn).
- **Fan-out:** ο relay είναι ο `on_tick` callback του `EtoroWsClient`. Σε κάθε tick: υπολόγισε `change_pct` (βλ. παρακάτω), και push σε **κάθε** browser client που έχει subscribe αυτό το id, ως:
  ```json
  { "instrumentId": 100000, "bid": 64990.0, "ask": 65010.0, "last": 65000.0, "change_pct": 1.2, "ts": "2026-06-04T..." }
  ```
- **change%:** `closing_provider` δίνει το prevClose (`officialClosingPrice`) ανά instrument (memoized από το υπάρχον `_fetch_closing`). `change_pct = (last - prevClose) / prevClose * 100` όταν `prevClose not in (None, 0)`. Clamp/guard: αν prevClose πολύ μικρό ώστε να βγάζει absurd (>±100%) → στείλε `null` αντί garbage.
- **Snapshot σε νέο subscriber:** όταν client κάνει `set_ids` με νέα ids, στείλε αμέσως το `last[id]` (αν υπάρχει) ώστε να μη μένει το κελί κενό μέχρι το πρώτο tick.
- **Browser protocol (η δική μας πλευρά):**
  - client → server: `{ "op": "set", "ids": [100000, 1001, ...] }` (το πλήρες set ορατών ids· στέλνεται σε κάθε tab/page/search change).
  - server → client: ticks (πάνω) + προαιρετικά `{ "op": "status", "state": "live"|"reconnecting"|"down" }`.

### Backend — lifespan (`main.py`)

- Ο `EtoroWsClient` + `PriceRelay` δημιουργούνται ως singletons στο lifespan startup **αλλά** ο upstream `client.start()` καλείται **lazy** στον πρώτο browser subscriber (ώστε χωρίς frontend να μην κρατάμε ανοιχτό eToro socket). Στο shutdown → `client.stop()` + cancel debounce tasks.
- Το υπάρχον 90s catalog-refresh loop **μένει** (τροφοδοτεί λίστα/metadata + το REST seed).

### Frontend — `usePriceStream` (`hooks/usePriceStream.ts`)

```typescript
type Tick = { bid: number|null; ask: number|null; last: number|null; change_pct: number|null; ts: string };
function usePriceStream(): {
  ticks: Map<number, Tick>;          // ή ένα store· re-render όταν αλλάζουν τα ορατά
  subscribe: (ids: number[]) => void; // στέλνει {op:"set", ids}
  status: "live" | "reconnecting" | "down";
}
```

- Ανοίγει WS προς `/ws/prices` (same-origin· vite proxy: πρόσθεση `"/ws": { target: "ws://localhost:8765", ws: true }`).
- **Reconnect:** backoff (1→2→4…30s)· στο reconnect ξαναστέλνει το τελευταίο `ids` set· κρατά τα τελευταία ticks (no flash).
- Merge: ο **ScreenerTable** παίρνει τα seed rows από το REST και κάνει overlay τα `ticks.get(instrument_id)` (bid/ask/last/change) με subtle flash highlight (πράσινο/κόκκινο fade) όταν αλλάζει η τιμή.

### Frontend — App integration

- Μετά το `fetchCategory(category, {page,...})`, κάλεσε `subscribe(rows.map(r => r.instrument_id))`.
- Σε αλλαγή tab/page/search → νέο `subscribe(newIds)` (το backend κάνει diff/unsubscribe τα παλιά).
- **Το 30s `refetchInterval`** της category query χαλαρώνει σε αργό safety poll (π.χ. 5 min) — η λίστα/metadata δεν αλλάζει συχνά· οι τιμές έρχονται από WS. Το catalog-status indicator γίνεται «Live» (WS state) αντί «updated Xs ago».
- **Κλειστά:** για rows με `is_open=false`, δεν περιμένουμε ticks· δείχνουμε seed price + «Closed» badge (όπως ήδη η γκρι τελίτσα).

## Data flow

```
tab=Crypto,page=1
  → REST fetchCategory → seed rows (bid/ask/last/change + prevClose + is_open)
  → usePriceStream.subscribe([ids])  → WS {op:"set", ids}
backend: refcount union += ids → EtoroWsClient.subscribe(new) → Subscribe(snapshot=true)
eToro → ticks {messages:[{topic, content}]} → parse → change% → fan-out
  → browser merge → ScreenerTable κελιά bid/ask/last/change ενημερώνονται live (flash)
change page/tab → subscribe(newIds); old ids refcount→0 → debounced upstream Unsubscribe
```

## Error handling

| Σενάριο | Συμπεριφορά |
|---|---|
| Upstream auth-fail / disconnect | backend reconnect+resubscribe· browsers κρατούν τελευταία ticks· status → "reconnecting" |
| Browser WS drop | frontend reconnect + resend ids· κρατά τελευταία ticks (no flash) |
| Instrument χωρίς tick / rate-limit | fallback στο REST seed (current_rate) — graceful degrade |
| Market closed (`is_open=false`) | κανένα tick· seed price + "Closed" badge |
| Keys λάθος/missing | relay κάτω (status "down")· ο screener δουλεύει σε REST seed· header "live (delayed)" |
| prevClose ≈ 0 / absurd change | στείλε `change_pct=null` αντί garbage |

## Testing (offline, mocked)

1. **`test_etoro_ws_client.py`** — με **fake socket** (in-memory): Authenticate πρώτο μήνυμα· Subscribe/Unsubscribe σωστά topics· parse `{messages:[{type:"Trading.Instrument.Rate", content:"{...}"}]}` → σωστό `Tick`· reconnect ξανα-Authenticate+Subscribe το active set· άγνωστα `type` αγνοούνται.
2. **`test_price_relay.py`** — με **fake EtoroWsClient**: ref-count diff (δύο clients, overlapping ids → upstream subscribe μία φορά)· refcount→0 → debounced unsubscribe· tick → fan-out μόνο στους subscribers του id· change% από prevClose (+ null όταν prevClose 0/absurd)· snapshot `last` σε νέο subscriber.
3. **`test_ws_prices_endpoint.py`** — FastAPI `TestClient.websocket_connect("/ws/prices")`: στέλνεις `{op:"set", ids:[...]}`, λαμβάνεις snapshot tick από το fake upstream· detach μειώνει refcounts.
4. **Frontend `usePriceStream.test.ts`** (vitest, mock WebSocket): tick → ενημερώνει το map· reconnect → resend ids· κρατά τελευταία ticks.
5. **ScreenerTable** ήδη τεσταρισμένο (renders bid/ask/change)· πρόσθεση test ότι κάνει overlay tick πάνω σε seed row.
6. **e2e** (Playwright): επέκταση happy-path — μετά από προσομοιωμένο tick, ένα price cell αλλάζει (ή live verify σε ώρα αγοράς).

## Dependencies

- Backend: `websockets` (async WS client). Καμία άλλη.
- Frontend: καμία νέα (native `WebSocket`).

## Επιπτώσεις

- Πραγματικά live bid/ask/last/change στον screener (όχι «—», όχι 30s καθυστέρηση)· σωστό change% (live, με guard στα absurd).
- Reuse: το ίδιο `EtoroWsClient`/`PriceRelay` θα τροφοδοτήσει το **Spec 2 (Portfolio live P&L)** — οι θέσεις (REST per-user) re-priced από το ίδιο shared market-data feed.
- Multitenant-ready: market data μένει ένα shared connection· per-user private feeds (orders/positions) προστίθενται χωρίς να αλλάξει αυτό το relay.
