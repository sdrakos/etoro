# Design: Yahoo Finance ως data source στο `trader/`

**Ημερομηνία:** 2026-06-02
**Κατάσταση:** Approved — έτοιμο για implementation plan

## Στόχος

Να μπορεί το `trader/` backtesting framework να τραβάει τιμές OHLCV από το Yahoo
Finance (δωρεάν, χωρίς API key), με τον ίδιο τρόπο που σήμερα τραβάει από το
Massive/Polygon SDK. Ίδιο cache-aside μοτίβο, ίδιο σχήμα DataFrame στην έξοδο,
καμία αλλαγή στο πώς το χρησιμοποιούν strategies/engine.

Το Yahoo γίνεται το **προεπιλεγμένο** source (δεν χρειάζεται key). Το Massive
παραμένει διαθέσιμο μέσω flag.

## Μη-στόχοι (YAGNI)

- Δεν υποστηρίζουμε intraday — μένει `timespan="day"` όπως και τώρα.
- Δεν προσθέτουμε env var για επιλογή source· η επιλογή γίνεται με flag/param.
- Δεν αλλάζουμε strategies, engine, ή το `back/` FastAPI layer.
- Δεν προσθέτουμε άλλους providers· μόνο abstraction που επιτρέπει μελλοντική
  προσθήκη χωρίς να ξαναγραφτεί η cache λογική.

## Αρχιτεκτονική — provider abstraction

Σήμερα το Massive fetch είναι hardcoded μέσα στο `loader.py`. Το σπάμε σε μικρά
source modules με κοινό interface, και ο `loader` γίνεται source-agnostic
ορχήστρα του cache-aside.

```
trader/data/
  loader.py          # cache-aside ορχήστρα — source-agnostic
  cache.py           # SQLite (PK περιλαμβάνει πλέον source)
  sources/
    __init__.py
    massive.py       # fetch_bars(...) — μεταφορά από loader.py σήμερα
    yahoo.py         # fetch_bars(...) — yfinance, auto_adjust=True
```

### Source interface

Κάθε source module εκθέτει μία συνάρτηση με σταθερή υπογραφή:

```python
def fetch_bars(ticker: str, start: date, end: date, timespan: str = "day") -> list[dict]:
    """Επιστρέφει bar rows έτοιμα για cache.upsert(). Κάθε dict έχει τα κλειδιά:
    ticker, timestamp (ms epoch, UTC), open, high, low, close, volume, vwap.
    'vwap' μπορεί να είναι None (το Yahoo δεν το δίνει)."""
```

- **`sources/massive.py`** — ό,τι κάνει σήμερα ο βρόχος `_client().list_aggs(...)`
  μέσα στο `loader.py`, μετακινημένο εδώ. Χρησιμοποιεί `get_massive_key()`.
- **`sources/yahoo.py`** — `yfinance.Ticker(ticker).history(start=..., end=...,
  interval="1d", auto_adjust=True)`. Μετατρέπει το DataFrame σε bar dicts:
  - index (ημερομηνία) → `timestamp` σε ms epoch UTC
  - `Open/High/Low/Close/Volume` → `open/high/low/close/volume`
  - `vwap` = `None`
  - `auto_adjust=True` ώστε οι τιμές να είναι adjusted (συνεπείς με τα backtests).
  - Το `end` του yfinance είναι exclusive· προσθέτουμε +1 ημέρα ώστε να
    συμπεριλαμβάνεται η τελική ημερομηνία (ίδια συμπεριφορά με Massive).

## Public API

```python
load_bars(ticker, start, end, timespan="day", source="yahoo") -> pd.DataFrame
```

- `source="yahoo"` (default) ή `"massive"`.
- Η έξοδος (DataFrame indexed σε datetime UTC, στήλες open/high/low/close/volume/vwap)
  παραμένει **πανομοιότυπη** ανεξαρτήτως source.
- Ο `loader` διαλέγει το source module, υπολογίζει gaps **ανά source** (μέσω του
  `cache.coverage(ticker, timespan, source)`), τραβάει μόνο τα κενά, κάνει upsert
  με το `source`, και επιστρέφει το query.

## Cache isolation

Το cache γίνεται keyed σε `(ticker, timestamp, timespan, source)` ώστε δεδομένα
από διαφορετικούς providers να μην πατάει το ένα το άλλο (οι adjusted τιμές
διαφέρουν ελαφρώς μεταξύ providers).

### Schema (νέο)

```sql
CREATE TABLE IF NOT EXISTS bars (
    ticker     TEXT NOT NULL,
    timestamp  INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, vwap REAL,
    adjusted   INTEGER DEFAULT 1,
    timespan   TEXT DEFAULT 'day',
    source     TEXT NOT NULL DEFAULT 'massive',
    PRIMARY KEY (ticker, timestamp, timespan, source)
);
CREATE INDEX IF NOT EXISTS idx_bars_ticker_range
    ON bars(ticker, timespan, source, timestamp);
```

### Migration (αυτόματη, μιας φοράς, στο `Cache.__init__`)

1. Έλεγχος αν ο πίνακας `bars` έχει στήλη `source` (`PRAGMA table_info(bars)`).
2. Αν λείπει (παλιά βάση): rebuild
   - `CREATE TABLE bars_new (... νέο schema ...)`
   - `INSERT INTO bars_new (...) SELECT ..., 'massive' FROM bars`
     (όλα τα υπάρχοντα δεδομένα ήρθαν από Massive)
   - `DROP TABLE bars; ALTER TABLE bars_new RENAME TO bars;`
   - recreate index.
3. Αν υπάρχει ήδη: τίποτα.

Η migration τυλίγεται σε transaction.

### Μέθοδοι του `Cache`

Όλες αποκτούν παράμετρο `source: str` (με συνετό default όπου χρειάζεται):

- `upsert(bars, timespan="day", source="massive")` — γράφει το source στη στήλη·
  το `ON CONFLICT` target γίνεται `(ticker, timestamp, timespan, source)`.
- `query(ticker, start_ms, end_ms, timespan="day", source="massive")`
- `coverage(ticker, timespan="day", source="massive")`
- `clear(ticker, timespan="day", source=None)` — `source=None` → σβήνει όλα τα
  sources για τον ticker (διατηρεί την τρέχουσα "καθάρισε τον ticker" σημασία).
- `list_tickers(timespan="day")` — προσθέτει στήλη `source` στο GROUP BY/έξοδο
  ώστε το `cache-list` να δείχνει ανά source.

## Config: lazy `MASSIVE_KEY`

Σήμερα το `config.py` πετάει `RuntimeError` στο import αν λείπει το `MASSIVE_KEY`.
Με το Yahoo ως default αυτό χαλάει τη χρήση χωρίς key. Αλλαγή:

- Στο import: φόρτωσε το key από `back/.env` σε module-level μεταβλητή, **χωρίς
  raise** (μπορεί να είναι `None`).
- Νέα συνάρτηση `get_massive_key() -> str` που κάνει raise `RuntimeError` με το
  σαφές μήνυμα **μόνο όταν κληθεί** (δηλ. μόνο όταν `source="massive"`).
- Το `sources/massive.py` καλεί `get_massive_key()`.

## CLI

Προστίθεται flag `--source {yahoo,massive}` (default `yahoo`) στα subcommands που
τραβάνε δεδομένα:

- `fetch` — `--source` περνάει στο `load_bars`.
- `backtest`, `sweep` — `--source` περνάει στο `load_bars` για κάθε ticker.
- `cache-list` — δείχνει το source ανά γραμμή.
- `cache-clear` — προαιρετικό `--source` (default: όλα τα sources του ticker).

Το help του `fetch` αλλάζει από "from Massive" σε "from Yahoo/Massive".

## Dependencies

`trader/requirements.txt`: προσθήκη `yfinance>=1.4` (ήδη installed locally: 1.4.1).

## Testing (offline, όπως οι υπάρχοντες tests)

Όλα τα tests τρέχουν χωρίς δίκτυο· το yfinance γίνεται mock.

1. **`test_yahoo_source.py`** — `sources.yahoo.fetch_bars` με mocked
   `yfinance.Ticker(...).history()` που επιστρέφει γνωστό DataFrame· επαλήθευση
   ότι τα bar dicts έχουν σωστά κλειδιά, σωστό ms timestamp (UTC), `vwap=None`,
   και ότι το exclusive `end` καλύπτει την τελική ημέρα.
2. **`test_cache_source.py`** — cache isolation: upsert ίδιου ticker/timestamp με
   `source="massive"` και `source="yahoo"` με διαφορετικές τιμές· `query` ανά
   source επιστρέφει τις σωστές, χωρίς ανάμειξη/overwrite.
3. **`test_cache_migration.py`** — δημιουργία SQLite με το **παλιό** schema (χωρίς
   `source`) + μερικά rows· άνοιγμα με `Cache(...)` αναβαθμίζει το schema και τα
   παλιά rows εμφανίζονται ως `source='massive'`.
4. **`test_loader_dispatch.py`** — `load_bars(..., source="yahoo")` καλεί το yahoo
   `fetch_bars` (mocked) και όχι το massive· cache-aside: δεύτερη κλήση στο ίδιο
   range δεν ξανακαλεί το source.

## Files touched (σύνοψη)

| Αρχείο | Αλλαγή |
|---|---|
| `trader/data/sources/__init__.py` | νέο (package) |
| `trader/data/sources/yahoo.py` | νέο — `fetch_bars()` με yfinance |
| `trader/data/sources/massive.py` | νέο — μεταφορά Massive fetch από `loader.py` |
| `trader/data/loader.py` | `source` param + dispatch· cache calls με source |
| `trader/data/cache.py` | source στο PK + migration + παράμετρος σε μεθόδους |
| `trader/config.py` | lazy `get_massive_key()`· χωρίς raise στο import |
| `trader/cli.py` | flag `--source` σε fetch/backtest/sweep· cache-list/clear |
| `trader/requirements.txt` | `yfinance>=1.4` |
| `trader/tests/test_yahoo_source.py` | νέο |
| `trader/tests/test_cache_source.py` | νέο |
| `trader/tests/test_cache_migration.py` | νέο |
| `trader/tests/test_loader_dispatch.py` | νέο |

## Επιπτώσεις / σημεία προσοχής

- Η αλλαγή του default σε `yahoo` σημαίνει ότι υπάρχοντα backtests χωρίς ρητό
  `--source` θα τραβήξουν **νέα** Yahoo δεδομένα (διαφορετικό source key) αντί να
  διαβάσουν τα ήδη-cached Massive δεδομένα. Αυτό είναι αναμενόμενο (isolation) και
  τεκμηριώνεται· όποιος θέλει τα παλιά δεδομένα βάζει `--source massive`.
- Το `back/` δεν επηρεάζεται — εξακολουθεί να χρησιμοποιεί Massive απευθείας.
- Το CLAUDE.md guard «`load_bars` only supports `timespan="day"`» παραμένει σε ισχύ
  και για το Yahoo.
