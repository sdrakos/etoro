# Design: Per-indicator settings modal (params + style)

**Ημερομηνία:** 2026-06-05
**Κατάσταση:** Approved — έτοιμο για implementation plan
**Σχέση:** Επεκτείνει το instrument chart (`docs/.../2026-06-05-instrument-chart*`). Κάθε δείκτης τεχνικής ανάλυσης αποκτά ένα **⚙️** που ανοίγει ένα **επαγγελματικό modal** (TradingView-style) όπου ο χρήστης ρυθμίζει τις **παραμέτρους** του (calcParams) και το **στυλ** (χρώματα γραμμών). Καθαρά frontend — καμία backend αλλαγή.

## Γιατί

Σήμερα οι δείκτες μπαίνουν/βγαίνουν με toggle αλλά τρέχουν με **σταθερές** default παραμέτρους. Ο χρήστης θέλει να αλλάζει π.χ. RSI 14→21, MA περιόδους, χρώματα — από επαγγελματικό modal, όπως στο TradingView. Το KLineCharts ήδη υποστηρίζει `calcParams` + `styles` + `overrideIndicator`.

## Αποφάσεις (κλειδωμένες)

- **Per-indicator gear** (TradingView-style): κάθε **ενεργός** δείκτης έχει ⚙️ → modal **μόνο** για αυτόν.
- **Inputs + Style tabs**: αριθμητικές παράμετροι (calcParams) + χρώματα γραμμών.
- **Live-apply**: κάθε αλλαγή εφαρμόζεται **αμέσως** στο chart (`overrideIndicator`)· + **Reset to defaults**.
- Καθαρά frontend· KLineCharts ήδη εγκατεστημένο.

## Μη-στόχοι (YAGNI)

- Όχι persistence/localStorage (κάθε chart tab ξεκινά από defaults — μελλοντικό).
- Όχι νέοι custom δείκτες πέρα από τους 7 υπάρχοντες (MA/EMA/BOLL/VOL/MACD/RSI/KDJ).
- Όχι style πέρα από χρώμα γραμμών (πάχος/τύπος γραμμής, bar colors για VOL/MACD = μελλοντικό).
- Καμία backend αλλαγή.

---

## Indicator model

```ts
export interface IndicatorConfig {
  name: string;
  calcParams: number[];   // οι περίοδοι του δείκτη
  colors: string[];       // ένα χρώμα ανά γραμμή (μπορεί να ≠ calcParams.length)
}
```

`lib/indicators.ts` — defaults (KLineCharts v9 calcParams + δικά μας χρώματα + param labels + πλήθος γραμμών):

| Δείκτης | calcParams (defaults) | param labels | lines (χρώματα) |
|---|---|---|---|
| MA | `[5,10,30,60]` | MA1/MA2/MA3/MA4 | 4 |
| EMA | `[6,12,20]` | EMA1/EMA2/EMA3 | 3 |
| BOLL | `[20,2]` | Period / StdDev | 3 (UP/MID/DN) |
| VOL | `[5,10,20]` | MA1/MA2/MA3 | 3 |
| MACD | `[12,26,9]` | Short / Long / Signal | 2 (DIF/DEA) |
| RSI | `[6,12,24]` | RSI1/RSI2/RSI3 | 3 |
| KDJ | `[9,3,3]` | K / D / J | 3 |

Default χρώματα (theme-friendly): `["#EFB90B","#935EBD","#2962FF","#E5436F"]` (παίρνουμε όσα χρειάζονται). Το `colors` είναι **ανεξάρτητο** από το `calcParams.length` (π.χ. BOLL 2 params αλλά 3 γραμμές).

```ts
export const INDICATORS = ["MA","EMA","BOLL","VOL","MACD","RSI","KDJ"] as const;
export function defaultConfig(name: string): IndicatorConfig;     // deep-clone από INDICATOR_DEFAULTS
export function paramLabels(name: string): string[];
export function klineStyles(colors: string[]): object;            // { lines: colors.map(c => ({ color: c })) }
```

## Αρχιτεκτονική

```
front/src/
  lib/indicators.ts                       # IndicatorConfig, INDICATOR_DEFAULTS, defaultConfig, klineStyles
  components/IndicatorSettingsModal.tsx    # νέο: modal (Inputs + Style) για έναν δείκτη
  components/ChartToolbar.tsx              # + ⚙️ ανά ενεργό δείκτη → onOpenSettings(name)
  components/Chart.tsx                      # indicators: IndicatorConfig[] → create/override/remove με calcParams+styles
  views/ChartView.tsx                      # state: Map<string,IndicatorConfig> + settingsFor + modal wiring
```

### `Chart.tsx` (αλλαγή prop + override)

- Prop: `indicators: IndicatorConfig[]` (αντί `string[]`).
- Reconcile effect: για κάθε config
  - αν δεν υπάρχει pane → `createIndicator({ name, calcParams, styles: klineStyles(colors) }, false, MAIN_OVERLAYS.includes(name) ? { id: "candle_pane" } : undefined)`· κράτα `paneId` + signature `JSON.stringify({calcParams,colors})`.
  - αν υπάρχει αλλά **άλλαξε** η signature → `overrideIndicator({ name, calcParams, styles: klineStyles(colors) }, paneId)`.
- Όσα δεν είναι πια στο `indicators` → `removeIndicator(paneId, name)`.
- Track: `Map<name, { paneId: string; sig: string }>`.

### `IndicatorSettingsModal.tsx` (νέο)

Props: `{ name: string; config: IndicatorConfig; onApply: (c: IndicatorConfig) => void; onReset: () => void; onClose: () => void }`.
- Overlay (fixed, dimmed) + κεντρικό panel (dark tokens). `role="dialog"`, `aria-modal`, focus trap, **Esc** + click-outside κλείνουν.
- Header: «`{name}` settings» + ✕.
- **Tabs** «Inputs | Style»:
  - *Inputs*: για κάθε `calcParams[i]` ένα `<input type="number">` με label `paramLabels(name)[i]`. Αλλαγή → `onApply({ ...config, calcParams: nextParams })` (live).
  - *Style*: για κάθε `colors[i]` ένα `<input type="color">` (+ swatch). Αλλαγή → `onApply({ ...config, colors: nextColors })`.
- Footer: **Reset to defaults** (`onReset`) + **Close**.

### `ChartToolbar.tsx`

- Νέο prop `onOpenSettings: (name: string) => void`.
- Για κάθε δείκτη που είναι **active**, δίπλα στο toggle ένα μικρό **⚙️** button → `onOpenSettings(name)` (aria-label `«{name} settings»`). Ανενεργοί δείκτες: κανένα gear.

### `ChartView.tsx`

- State: `const [configs, setConfigs] = useState<Map<string, IndicatorConfig>>(new Map([["MA",defaultConfig("MA")],["VOL",defaultConfig("VOL")]]))`.
- `const [settingsFor, setSettingsFor] = useState<string | null>(null)`.
- `toggle(name)`: αν υπάρχει → delete (+ αν `settingsFor===name` → null)· αλλιώς → `set(name, defaultConfig(name))`.
- `onOpenSettings(name)` → `setSettingsFor(name)`.
- `applyConfig(name, cfg)` → `setConfigs(prev => new Map(prev).set(name, cfg))`.
- Περνά `indicators={[...configs.values()]}` στο `Chart`, `active={new Set(configs.keys())}` + `onOpenSettings` στο `ChartToolbar`.
- Όταν `settingsFor` → render `<IndicatorSettingsModal name=settingsFor config=configs.get(settingsFor) onApply=(c)=>applyConfig(settingsFor,c) onReset=()=>applyConfig(settingsFor, defaultConfig(settingsFor)) onClose=()=>setSettingsFor(null) />`.

## Data flow

```
toolbar ⚙️(RSI) → setSettingsFor("RSI") → modal (config RSI)
  Inputs: period 6→9 → onApply({name:"RSI", calcParams:[9,12,24], colors})
    → configs.set("RSI", cfg) → Chart: signature changed → overrideIndicator({name,calcParams,styles}, paneId) → instant
  Style: χρώμα γραμμής → onApply({...cfg, colors:[...]}) → overrideIndicator(styles)
  Reset → applyConfig("RSI", defaultConfig("RSI"))
  Close → setSettingsFor(null)
```

## Error handling

- Άκυρη αριθμητική τιμή (κενό/NaN) στο Inputs → αγνοείται μέχρι να γίνει έγκυρος θετικός αριθμός (το input δεν σπάει τον δείκτη· KLineCharts θα αγνοήσει/clamp).
- Δείκτης που έγινε toggle-off ενώ το modal ανοιχτό → το modal κλείνει (`settingsFor=null`).
- KLineCharts `overrideIndicator` σε pane που δεν υπάρχει (race) → no-op (guard στο Chart).

## Testing (offline, KLineCharts mocked)

1. `indicators.test.ts`: `defaultConfig` επιστρέφει σωστά calcParams/colors ανά δείκτη + **deep clone** (mutating το ένα δεν αλλάζει τα defaults)· `klineStyles(colors)` → `{lines:[{color},...]}`.
2. `IndicatorSettingsModal.test.tsx`: renders inputs (= calcParams) + color pickers (= colors)· αλλαγή number → `onApply` με updated calcParams· tab switch Inputs↔Style· Reset → `onReset`· Esc/✕ → `onClose`.
3. `Chart.test.tsx` (update): prop τώρα `IndicatorConfig[]`· create καλεί `createIndicator` με `{name,calcParams,styles}`· αλλαγή calcParams στο ίδιο render → `overrideIndicator` κλήθηκε με τα νέα params.
4. `ChartToolbar.test.tsx` (update): active δείκτης δείχνει ⚙️ → click → `onOpenSettings(name)`.
5. `ChartView` (integration): ⚙️ → modal εμφανίζεται· αλλαγή param → το config στο Map αλλάζει (το βλέπουμε μέσω του mocked Chart/overrideIndicator).

## Dependencies

Καμία νέα.

## Επιπτώσεις

- Επαγγελματικός έλεγχος δεικτών (params + χρώματα) ανά δείκτη, instant-apply — σαν TradingView.
- Το indicator model γίνεται config (από string) — ανοίγει τον δρόμο για persistence/style-tab επεκτάσεις αργότερα χωρίς αναδόμηση.
- Reuse του υπάρχοντος Chart/Toolbar/ChartView· καμία backend/data αλλαγή.
