# Design: Professional interactive instrument chart (KLineCharts)

**Ημερομηνία:** 2026-06-05
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Νέα QUANTIQ οθόνη. Κλικ σε μια μετοχή (Screener ή Portfolio) → ανοίγει **νέο browser tab** με επαγγελματικό candlestick chart, δείκτες τεχνικής ανάλυσης, και live ενημέρωση από το υπάρχον `/ws/prices` relay. Δεν αλλάζει τίποτα από το screener/portfolio/WS — μόνο προσθέτει routing + ένα candles endpoint + το chart view.

## Γιατί

Ο χρήστης βλέπει live τιμές σε λίστες αλλά δεν μπορεί να δει **γράφημα** μιας μετοχής. Θέλει: κλικ σε μετοχή → **καινούργιο παράθυρο** με **διαδραστικό** (zoom/pan/crosshair), **επαγγελματικό** chart που έχει **δείκτες τεχνικής ανάλυσης**. Το eToro candles endpoint υπάρχει ήδη (επιβεβαιωμένο live: OHLCV ανά instrument, intervals).

## Αποφάσεις (κλειδωμένες)

- **Νέο browser tab** μέσω route `/chart/:instrumentId` + `window.open(...)` (όχι in-app modal). Πολλά γραφήματα ανοιχτά ταυτόχρονα, σαν trading terminal.
- **KLineCharts** (TradingView-style) — έχει **ενσωματωμένους δείκτες** (MA/EMA/BOLL/MACD/RSI/KDJ/VOL) + drawing tools, οπότε λιγότερος κώδικας για πλήρη TA.
- **Data = eToro candles** (server client / demo, app keys), όπως όλο το QUANTIQ. Όχι Massive.
- **Live last-candle update** από το **υπάρχον** `/ws/prices` relay (reuse `usePriceStream`).
- **Naming για αποφυγή σύγκρουσης:** backend prefix `/charts` (plural) ≠ frontend route `/chart` (singular).

## Μη-στόχοι (YAGNI)

- Όχι order placement / trading από το chart.
- Όχι save/load chart layouts, όχι multi-symbol compare.
- Όχι Massive/Polygon data — μόνο eToro candles.
- Καμία αλλαγή στο `/ws/prices` relay, screener, ή portfolio.

---

## eToro candles (επιβεβαιωμένο live shape)

`GET /api/v1/market-data/instruments/{id}/history/candles/{dir}/{interval}/{count}` →
```json
{ "interval": "OneDay",
  "candles": [ { "instrumentId": 1001,
                 "candles": [ {"fromDate":"2026-06-05T00:00:00Z","open":311.11,"high":311.68,"low":310.15,"close":310.57,"volume":10115.0}, … ] } ] }
```
- **Διπλά nested**: το OHLCV list είναι `data["candles"][0]["candles"]`.
- `dir=desc` → newest-first· το frontend (KLineCharts) θέλει **ascending** → αντιστρέφουμε.
- `volume` μπορεί να είναι `null` (π.χ. crypto). `fromDate` ISO-8601 → epoch ms.
- Intervals (eToro names): `OneMinute, FiveMinutes, FifteenMinutes, OneHour, FourHours, OneDay, OneWeek`.

---

## Αρχιτεκτονική

```
front/
  src/main.tsx                 # + BrowserRouter
  src/AppRoutes.tsx            # routes: "/" → <App/>, "/chart/:instrumentId" → <ChartView/>
  src/views/ChartView.tsx      # standalone chart page (νέο tab)
  src/components/Chart.tsx      # KLineCharts wrapper (init/apply/update/indicators)
  src/components/ChartToolbar.tsx  # timeframe + indicator toggles
  src/api/chart.ts             # fetchChart(id, interval)
  src/hooks/useChartData.ts    # TanStack Query
  src/lib/intervals.ts         # UI timeframe ↔ eToro interval (pure)
  src/lib/openChart.ts         # window.open('/chart/'+id)  (pure-ish util)
  src/vite.config.ts           # + "/charts" proxy
back/
  routers/chart.py             # GET /charts/{instrument_id}
  main.py                      # include chart.router
```

### Backend — `routers/chart.py`

```python
router = APIRouter(prefix="/charts", tags=["charts"])

class Candle(BaseModel):
    time: int        # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

class ChartResponse(BaseModel):
    instrument_id: int
    symbol: Optional[str] = None
    name: Optional[str] = None
    interval: str
    candles: list[Candle]   # ascending by time
```

**`GET /charts/{instrument_id}`** params: `interval="OneDay"`, `count=300` (clamp 1..1000), `account="demo"`.
1. `client = get_server_client()` (503 αν λείπουν keys).
2. `raw = client.request("GET", f"/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/{interval}/{count}")`.
3. `inner = (raw.get("candles") or [{}])[0].get("candles") or []` (το διπλό nesting).
4. map κάθε → `Candle(time=<fromDate→epoch ms>, open, high, low, close, volume)`, **πέτα** όσα έχουν None σε open/high/low/close, **sort ascending** by time.
5. enrich symbol/name από `EtoroCatalog(screener.CATALOG_DB).get_by_instrument_ids([instrument_id])`.
6. return `ChartResponse`.

`fromDate→epoch ms`: parse ISO-8601 (`datetime.fromisoformat` με `Z`→`+00:00`) → `int(dt.timestamp()*1000)`.

`main.py`: `from routers import chart` + `app.include_router(chart.router)`.

### Frontend — routing

- `react-router-dom`. `main.tsx` wrap σε `<BrowserRouter>`· `AppRoutes`:
  ```tsx
  <Routes>
    <Route path="/" element={<App />} />
    <Route path="/chart/:instrumentId" element={<ChartView />} />
  </Routes>
  ```
- `lib/openChart.ts`: `export const openChart = (id: number) => window.open(`/chart/${id}`, "_blank", "noopener");`

### Frontend — `lib/intervals.ts` (pure)

```typescript
export interface Timeframe { id: string; label: string; etoro: string; }
export const TIMEFRAMES: Timeframe[] = [
  { id: "5m",  label: "5m",  etoro: "FiveMinutes" },
  { id: "15m", label: "15m", etoro: "FifteenMinutes" },
  { id: "1h",  label: "1H",  etoro: "OneHour" },
  { id: "4h",  label: "4H",  etoro: "FourHours" },
  { id: "1d",  label: "1D",  etoro: "OneDay" },
  { id: "1w",  label: "1W",  etoro: "OneWeek" },
];
export function toEtoroInterval(id: string): string;  // default "OneDay"
```

### Frontend — `api/chart.ts` + `useChartData.ts`

- `fetchChart(id, interval): Promise<ChartResponse>` → `GET /charts/{id}?interval={interval}&count=300`.
- `useChartData(id, interval)` → `useQuery(["chart", id, interval], …)`.
- TS types `Candle`, `ChartResponse` mirror του backend.

### Frontend — `components/Chart.tsx` (KLineCharts wrapper)

- `init(ref)` στο mount, `dispose` στο unmount. Dark theme styling (κοντά στα tokens).
- `applyNewData(candles)` όταν αλλάζουν τα data· KLineCharts candle = `{ timestamp, open, high, low, close, volume }`.
- `createIndicator(name, isStack, {id:pane})` / `removeIndicator` για toggles.
- expose imperative API (ref ή callbacks) ώστε το ChartToolbar να ανάβει/σβήνει δείκτες και το live-update να κάνει `updateData(lastCandle)`.

### Frontend — `components/ChartToolbar.tsx`

- Timeframe buttons (από `TIMEFRAMES`) → `onTimeframe(id)`.
- Indicator toggles: main-overlay (MA, EMA, BOLL) + sub-pane (VOL, MACD, RSI, KDJ). Default ενεργά: **MA + VOL**. State: `Set<string>` ενεργών δεικτών → callbacks add/remove.

### Frontend — `views/ChartView.tsx`

- `const { instrumentId } = useParams()`· `const [tf, setTf] = useState("1d")`.
- `const { data, isLoading, isError } = useChartData(id, toEtoroInterval(tf))`.
- header: symbol/name + live τιμή· `<ChartToolbar/>` + `<Chart/>`.
- **Live**: `const stream = usePriceStream(); useEffect → stream.subscribe([id])`· σε νέο tick → `chart.updateData({timestamp: now-bucket, open/high/low/close from last+tick})` — ενημερώνει το τελευταίο candle (close, high=max, low=min).
- error/empty states.

## Data flow

```
[Screener/Portfolio row click] → openChart(instrument_id) → window.open('/chart/100000')
[ChartView νέο tab] → GET /charts/100000?interval=OneDay&count=300 → {symbol,name,candles[]}
  → Chart.applyNewData(candles) + default indicators (MA, VOL)
  → timeframe change → useChartData refetch → applyNewData
  → usePriceStream.subscribe([100000]) → tick → Chart.updateData(last candle) live
```

## Error handling

| Σενάριο | Συμπεριφορά |
|---|---|
| Λείπουν keys | `get_server_client` → 503· ChartView error banner |
| Instrument χωρίς candles | `candles: []` → «No chart data for this instrument» |
| Άγνωστο id / no catalog match | symbol/name null → header δείχνει `#id`· chart δουλεύει αν υπάρχουν candles |
| Άκυρο interval | eToro 4xx → 502 από τον client· UI error· default «1D» |
| Closed market | στατικό chart· live tick μένει στο τελευταίο close |
| Backend down (νέο tab) | error banner «Is the backend running on :8765?» |

## Testing (offline, mocked)

1. **`test_chart.py`** (backend): mock `get_server_client` που επιστρέφει το διπλά-nested candles shape → endpoint **flatten** + **ascending sort** + **epoch ms** + drop incomplete + catalog enrich (symbol/name)· άδεια candles → `[]`.
2. **Frontend** (vitest):
   - `intervals.ts`: `toEtoroInterval` mapping + default.
   - `openChart`: καλεί `window.open` με `/chart/{id}` (mock window.open).
   - `chart.ts` api: URL + params· `useChartData` query.
   - `ChartToolbar`: renders timeframes + indicator toggles, fires callbacks.
   - `ChartView`: loads → header symbol + container· **KLineCharts mock-άρεται** (jsdom χωρίς canvas) — τεστάρουμε wiring (applyNewData κλήθηκε με candles, timeframe change → refetch), όχι pixels.
   - Row-click wiring: ScreenerTable/PortfolioTable το ticker/row είναι clickable → `openChart` (mock).

## Dependencies

- Frontend: `klinecharts`, `react-router-dom`. Backend: καμία νέα.

## Επιπτώσεις

- Κλικ σε μετοχή → επαγγελματικό, διαδραστικό chart με δείκτες σε νέο tab — σαν trading terminal.
- Reuse: eToro candles (ήδη δουλεύει), `usePriceStream`/`/ws/prices` relay (live last candle), catalog (symbol/name).
- Το routing (`react-router-dom`) ανοίγει τον δρόμο για επόμενες deep-linkable οθόνες.
