# Yahoo Finance Data Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Yahoo Finance as the default (free, keyless) price source for the `trader/` backtesting framework, with Massive/Polygon available behind a `--source` flag, sharing the same cache-aside loader and DataFrame shape.

**Architecture:** Extract the hardcoded Massive fetch out of `loader.py` into a `trader/data/sources/` package where each provider exposes the same `fetch_bars()` interface. The `loader` stays source-agnostic and orchestrates the cache. The SQLite cache gains `source` in its primary key (with an automatic one-time migration of existing Massive data). `MASSIVE_KEY` becomes lazy so the framework runs keyless on Yahoo.

**Tech Stack:** Python 3.11+, yfinance (Yahoo), massive/polygon SDK, SQLite, pandas, pytest (offline, mocked).

---

## File Structure

| File | Responsibility |
|---|---|
| `trader/data/cache.py` | SQLite store; PK now includes `source`; auto-migrates old DBs; all methods take `source` |
| `trader/config.py` | Loads `MASSIVE_KEY` without raising; `get_massive_key()` raises only on use |
| `trader/data/sources/__init__.py` | Marks the package |
| `trader/data/sources/massive.py` | `fetch_bars()` via massive/polygon SDK (moved out of loader) |
| `trader/data/sources/yahoo.py` | `fetch_bars()` via yfinance, `auto_adjust=True` |
| `trader/data/loader.py` | Source-agnostic cache-aside; `load_bars(..., source="yahoo")` dispatches |
| `trader/engine/runner.py` | `run_backtest(..., source="yahoo")` plumbs source to `load_bars` |
| `trader/cli.py` | `--source {yahoo,massive}` on fetch/backtest/sweep; cache-list shows source; cache-clear optional `--source` |
| `trader/requirements.txt` | adds `yfinance>=1.4` |
| `trader/tests/test_cache_migration.py` | old-schema DB upgrades, rows become `massive` |
| `trader/tests/test_cache_source.py` | two sources for same ticker stay isolated |
| `trader/tests/test_yahoo_source.py` | yfinance mapping (mocked) |
| `trader/tests/test_loader_dispatch.py` | loader picks the right source; cache-aside avoids refetch |

The existing `trader/tests/test_cache.py` calls `upsert`/`query`/`coverage` without a `source` argument — those default to `"massive"`, so the suite keeps passing unchanged.

---

### Task 1: Cache — `source` in primary key + auto-migration

**Files:**
- Modify: `trader/data/cache.py`
- Test: `trader/tests/test_cache_migration.py` (create), `trader/tests/test_cache_source.py` (create)

- [ ] **Step 1: Write the migration failing test**

Create `trader/tests/test_cache_migration.py`:

```python
import sqlite3
import pandas as pd
from trader.data.cache import Cache

OLD_SCHEMA = """
CREATE TABLE bars (
    ticker TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, vwap REAL,
    adjusted INTEGER DEFAULT 1,
    timespan TEXT DEFAULT 'day',
    PRIMARY KEY (ticker, timestamp, timespan)
);
"""


def test_old_db_migrates_and_tags_rows_as_massive(tmp_path):
    db = tmp_path / "cache.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(OLD_SCHEMA)
        conn.execute(
            "INSERT INTO bars (ticker, timestamp, open, high, low, close, volume, vwap, adjusted, timespan) "
            "VALUES ('AAPL', 1700000000000, 1, 1, 1, 1, 1, 1, 1, 'day')"
        )

    cache = Cache(db)  # opening triggers migration

    cols = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(bars)")]
    assert "source" in cols

    df = cache.query("AAPL", 0, 1_800_000_000_000, source="massive")
    assert len(df) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest trader/tests/test_cache_migration.py -v`
Expected: FAIL — `query()` got an unexpected keyword `source`, or no `source` column.

- [ ] **Step 3: Rewrite `cache.py` with new schema, migration, and source-aware methods**

Replace the entire contents of `trader/data/cache.py`:

```python
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    ticker     TEXT NOT NULL,
    timestamp  INTEGER NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    vwap       REAL,
    adjusted   INTEGER DEFAULT 1,
    timespan   TEXT DEFAULT 'day',
    source     TEXT NOT NULL DEFAULT 'massive',
    PRIMARY KEY (ticker, timestamp, timespan, source)
);
CREATE INDEX IF NOT EXISTS idx_bars_ticker_range
    ON bars(ticker, timespan, source, timestamp);
"""

_MIGRATE_ADD_SOURCE = """
ALTER TABLE bars RENAME TO bars_old;
CREATE TABLE bars (
    ticker     TEXT NOT NULL,
    timestamp  INTEGER NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    vwap       REAL,
    adjusted   INTEGER DEFAULT 1,
    timespan   TEXT DEFAULT 'day',
    source     TEXT NOT NULL DEFAULT 'massive',
    PRIMARY KEY (ticker, timestamp, timespan, source)
);
INSERT INTO bars (ticker, timestamp, open, high, low, close,
                  volume, vwap, adjusted, timespan, source)
    SELECT ticker, timestamp, open, high, low, close,
           volume, vwap, adjusted, timespan, 'massive'
    FROM bars_old;
DROP TABLE bars_old;
"""


class Cache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with sqlite3.connect(self.db_path) as conn:
            self._migrate(conn)
            conn.executescript(SCHEMA)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """One-time upgrade: add `source` to the PK of pre-existing DBs."""
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bars'"
        ).fetchone()
        if not exists:
            return  # fresh DB — SCHEMA creates the new table
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bars)")]
        if "source" in cols:
            return  # already migrated
        conn.executescript(_MIGRATE_ADD_SOURCE)

    def upsert(self, bars: Iterable[dict], timespan: str = "day",
               source: str = "massive") -> int:
        rows = [(b["ticker"], int(b["timestamp"]),
                 b.get("open"), b.get("high"), b.get("low"), b.get("close"),
                 b.get("volume"), b.get("vwap"), 1, timespan, source) for b in bars]
        if not rows:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO bars (ticker, timestamp, open, high, low, close,
                                  volume, vwap, adjusted, timespan, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, timestamp, timespan, source) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, vwap=excluded.vwap
            """, rows)
            return conn.total_changes

    def query(self, ticker: str, start_ms: int, end_ms: int,
              timespan: str = "day", source: str = "massive") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT timestamp, open, high, low, close, volume, vwap
                   FROM bars
                   WHERE ticker = ? AND timespan = ? AND source = ?
                     AND timestamp BETWEEN ? AND ?
                   ORDER BY timestamp""",
                conn, params=(ticker, timespan, source, start_ms, end_ms),
            )

    def coverage(self, ticker: str, timespan: str = "day",
                 source: str = "massive") -> tuple[int, int] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM bars "
                "WHERE ticker = ? AND timespan = ? AND source = ?",
                (ticker, timespan, source),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return (int(row[0]), int(row[1]))

    def clear(self, ticker: str, timespan: str = "day",
              source: str | None = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            if source is None:
                cur = conn.execute(
                    "DELETE FROM bars WHERE ticker = ? AND timespan = ?",
                    (ticker, timespan),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM bars WHERE ticker = ? AND timespan = ? AND source = ?",
                    (ticker, timespan, source),
                )
            return cur.rowcount

    def list_tickers(self, timespan: str = "day") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                "SELECT ticker, source, MIN(timestamp) AS min_ts, "
                "       MAX(timestamp) AS max_ts, COUNT(*) AS bar_count "
                "FROM bars WHERE timespan = ? "
                "GROUP BY ticker, source ORDER BY ticker, source",
                conn, params=(timespan,),
            )
```

- [ ] **Step 4: Run the migration test to verify it passes**

Run: `python -m pytest trader/tests/test_cache_migration.py -v`
Expected: PASS

- [ ] **Step 5: Write the cache-isolation failing test**

Create `trader/tests/test_cache_source.py`:

```python
from trader.data.cache import Cache


def test_two_sources_same_bar_do_not_collide(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    ts = 1_700_000_000_000
    cache.upsert([{"ticker": "AAPL", "timestamp": ts,
                   "open": 1, "high": 1, "low": 1, "close": 100.0,
                   "volume": 1, "vwap": 1}], source="massive")
    cache.upsert([{"ticker": "AAPL", "timestamp": ts,
                   "open": 1, "high": 1, "low": 1, "close": 200.0,
                   "volume": 1, "vwap": 1}], source="yahoo")

    m = cache.query("AAPL", 0, ts + 1, source="massive")
    y = cache.query("AAPL", 0, ts + 1, source="yahoo")
    assert len(m) == 1 and m.iloc[0]["close"] == 100.0
    assert len(y) == 1 and y.iloc[0]["close"] == 200.0


def test_coverage_is_per_source(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert([{"ticker": "AAPL", "timestamp": 1_700_000_000_000,
                   "open": 1, "high": 1, "low": 1, "close": 1,
                   "volume": 1, "vwap": 1}], source="yahoo")
    assert cache.coverage("AAPL", source="massive") is None
    assert cache.coverage("AAPL", source="yahoo") is not None
```

- [ ] **Step 6: Run isolation + full cache suite**

Run: `python -m pytest trader/tests/test_cache_source.py trader/tests/test_cache.py -v`
Expected: PASS (existing `test_cache.py` still green via `source="massive"` defaults).

- [ ] **Step 7: Commit**

```bash
git add trader/data/cache.py trader/tests/test_cache_migration.py trader/tests/test_cache_source.py
git commit -m "feat(trader): add source to cache key with auto-migration"
```

---

### Task 2: Config — lazy `MASSIVE_KEY`

**Files:**
- Modify: `trader/config.py`
- Test: covered indirectly; verify import works keyless via Step 2.

- [ ] **Step 1: Rewrite `config.py` to not raise at import**

Replace the body of `trader/config.py` (keep the path setup) so the raise moves into a function:

```python
"""Config: load MASSIVE_KEY from etoro/back/.env (reuse — no duplication)."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
ETORO_ROOT = PACKAGE_ROOT.parent
BACK_ENV = ETORO_ROOT / "back" / ".env"

load_dotenv(BACK_ENV)

MASSIVE_KEY = (
    os.getenv("MASSIVE_KEY")
    or os.getenv("MASSIVE_API_KEY")
    or os.getenv("POLYGON_API_KEY")
)


def get_massive_key() -> str:
    """Return the Massive/Polygon key, raising only when it's actually needed."""
    if not MASSIVE_KEY:
        raise RuntimeError(f"MASSIVE_KEY missing from {BACK_ENV}")
    return MASSIVE_KEY


CACHE_DIR = Path(os.getenv("ETORO_CACHE_DIR", Path.home() / ".etoro"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "cache.db"
```

- [ ] **Step 2: Verify the module imports without a key**

Run: `python -c "import trader.config as c; print('ok', bool(c.MASSIVE_KEY) or 'no-key')"`
Expected: prints `ok ...` with no traceback (works whether or not a key is present).

- [ ] **Step 3: Commit**

```bash
git add trader/config.py
git commit -m "refactor(trader): make MASSIVE_KEY lazy via get_massive_key()"
```

---

### Task 3: Sources package — `massive.py` + `yahoo.py`

**Files:**
- Create: `trader/data/sources/__init__.py`, `trader/data/sources/massive.py`, `trader/data/sources/yahoo.py`
- Test: `trader/tests/test_yahoo_source.py` (create)

- [ ] **Step 1: Write the Yahoo failing test**

Create `trader/tests/test_yahoo_source.py`:

```python
from datetime import date
from unittest import mock
import pandas as pd
import pytest


def _fake_history_df():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"]).tz_localize("UTC")
    return pd.DataFrame(
        {"Open": [10.0, 11.0], "High": [12.0, 13.0], "Low": [9.0, 10.0],
         "Close": [11.0, 12.0], "Volume": [1000.0, 2000.0]},
        index=idx,
    )


def test_yahoo_fetch_bars_maps_rows():
    from trader.data.sources import yahoo
    with mock.patch.object(yahoo, "yf") as yf_mock:
        yf_mock.Ticker.return_value.history.return_value = _fake_history_df()
        rows = yahoo.fetch_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3))

    assert len(rows) == 2
    first = rows[0]
    assert first["ticker"] == "AAPL"
    assert first["open"] == 10.0 and first["close"] == 11.0
    assert first["vwap"] is None
    # 2024-01-02 00:00 UTC in ms
    assert first["timestamp"] == 1_704_153_600_000


def test_yahoo_passes_exclusive_end_plus_one_day():
    from trader.data.sources import yahoo
    with mock.patch.object(yahoo, "yf") as yf_mock:
        yf_mock.Ticker.return_value.history.return_value = _fake_history_df()
        yahoo.fetch_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3))
        _, kwargs = yf_mock.Ticker.return_value.history.call_args
    assert kwargs["end"] == "2024-01-04"  # end + 1 day (yfinance end is exclusive)
    assert kwargs["start"] == "2024-01-02"
    assert kwargs["auto_adjust"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest trader/tests/test_yahoo_source.py -v`
Expected: FAIL — `trader.data.sources` does not exist.

- [ ] **Step 3: Create the sources package**

Create `trader/data/sources/__init__.py`:

```python
"""Price-source providers. Each module exposes `fetch_bars(ticker, start, end, timespan)`."""
```

Create `trader/data/sources/yahoo.py`:

```python
"""Yahoo Finance source via yfinance (free, no API key). Adjusted daily bars."""
from __future__ import annotations
import datetime as dt
from datetime import date, timedelta

import yfinance as yf


def fetch_bars(ticker: str, start: date, end: date,
               timespan: str = "day") -> list[dict]:
    """Return adjusted daily bar dicts ready for Cache.upsert().

    `end` is inclusive here; yfinance treats its `end` as exclusive, so we add
    one day. Timestamps are anchored to UTC midnight to match the cache convention.
    """
    if timespan != "day":
        raise NotImplementedError("Yahoo source supports timespan='day' only.")
    df = yf.Ticker(ticker).history(
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=True,
    )
    rows: list[dict] = []
    for idx, row in df.iterrows():
        ts = int(dt.datetime(idx.year, idx.month, idx.day,
                             tzinfo=dt.timezone.utc).timestamp() * 1000)
        rows.append({
            "ticker": ticker, "timestamp": ts,
            "open": float(row["Open"]), "high": float(row["High"]),
            "low": float(row["Low"]), "close": float(row["Close"]),
            "volume": float(row["Volume"]), "vwap": None,
        })
    return rows
```

Create `trader/data/sources/massive.py`:

```python
"""Massive/Polygon source via the REST SDK. Daily aggregate bars."""
from __future__ import annotations
from datetime import date
from functools import lru_cache

from trader.config import get_massive_key

try:
    from massive import RESTClient
except ImportError:
    from polygon import RESTClient


@lru_cache(maxsize=1)
def _client() -> "RESTClient":
    return RESTClient(api_key=get_massive_key())


def fetch_bars(ticker: str, start: date, end: date,
               timespan: str = "day") -> list[dict]:
    """Return daily bar dicts ready for Cache.upsert()."""
    bars = list(_client().list_aggs(
        ticker, 1, timespan,
        start.isoformat(), end.isoformat(),
        limit=50000,
    ))
    return [{
        "ticker": ticker, "timestamp": b.timestamp,
        "open": b.open, "high": b.high, "low": b.low, "close": b.close,
        "volume": b.volume, "vwap": getattr(b, "vwap", None),
    } for b in bars]
```

- [ ] **Step 4: Run the Yahoo test to verify it passes**

Run: `python -m pytest trader/tests/test_yahoo_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add trader/data/sources/ trader/tests/test_yahoo_source.py
git commit -m "feat(trader): add yahoo + massive source providers"
```

---

### Task 4: Loader — source-agnostic dispatch

**Files:**
- Modify: `trader/data/loader.py`
- Test: `trader/tests/test_loader_dispatch.py` (create)

- [ ] **Step 1: Write the dispatch failing test**

Create `trader/tests/test_loader_dispatch.py`:

```python
from datetime import date
from unittest import mock
import trader.data.loader as loader


def _two_bars(ticker):
    return [
        {"ticker": ticker, "timestamp": 1_704_153_600_000,
         "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1000, "vwap": None},
        {"ticker": ticker, "timestamp": 1_704_240_000_000,
         "open": 11, "high": 13, "low": 10, "close": 12, "volume": 2000, "vwap": None},
    ]


def test_load_bars_uses_yahoo_source(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DB", tmp_path / "cache.db")
    with mock.patch.object(loader.yahoo, "fetch_bars",
                           return_value=_two_bars("AAPL")) as y, \
         mock.patch.object(loader.massive, "fetch_bars") as m:
        df = loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3),
                              source="yahoo")
    assert y.called
    assert not m.called
    assert len(df) == 2


def test_load_bars_is_cache_aside(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DB", tmp_path / "cache.db")
    with mock.patch.object(loader.yahoo, "fetch_bars",
                           return_value=_two_bars("AAPL")) as y:
        loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="yahoo")
        loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="yahoo")
    assert y.call_count == 1  # second call served entirely from cache


def test_load_bars_rejects_unknown_source(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DB", tmp_path / "cache.db")
    import pytest
    with pytest.raises(ValueError):
        loader.load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3), source="bogus")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest trader/tests/test_loader_dispatch.py -v`
Expected: FAIL — `loader.yahoo` attribute does not exist / `source` not accepted.

- [ ] **Step 3: Rewrite `loader.py` to dispatch by source**

Replace the entire contents of `trader/data/loader.py`:

```python
"""Cache-aside loader: SQLite first, fetch missing range from the chosen source."""
from __future__ import annotations
import datetime as dt
import logging
from datetime import date
from typing import Optional
import pandas as pd

from trader.config import CACHE_DB
from trader.data.cache import Cache
from trader.data.sources import massive, yahoo

log = logging.getLogger(__name__)

_SOURCES = {"yahoo": yahoo, "massive": massive}


def _to_ms(d: date) -> int:
    return int(dt.datetime(d.year, d.month, d.day,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


def _gaps(coverage: Optional[tuple[int, int]],
          start_ms: int, end_ms: int) -> list[tuple[int, int]]:
    """Return list of (start_ms, end_ms) ranges the cache does NOT cover."""
    if coverage is None:
        return [(start_ms, end_ms)]
    cmin, cmax = coverage
    gaps = []
    if start_ms < cmin:
        gaps.append((start_ms, min(end_ms, cmin - 1)))
    if end_ms > cmax:
        gaps.append((max(start_ms, cmax + 1), end_ms))
    return gaps


def load_bars(ticker: str, start: date, end: date,
              timespan: str = "day", source: str = "yahoo") -> pd.DataFrame:
    """Cache-aside fetch from `source`. Returns DataFrame indexed by datetime (UTC)."""
    if timespan != "day":
        raise NotImplementedError(
            f"Only timespan='day' is supported in Phase 1 (got {timespan!r}). "
            "Intraday support requires datetime-precision gap calculation."
        )
    try:
        provider = _SOURCES[source]
    except KeyError:
        raise ValueError(
            f"unknown source: {source!r}. Choose from {sorted(_SOURCES)}."
        )

    cache = Cache(CACHE_DB)
    start_ms, end_ms = _to_ms(start), _to_ms(end)

    coverage = cache.coverage(ticker, timespan, source)
    gaps = _gaps(coverage, start_ms, end_ms)

    for gap_start, gap_end in gaps:
        gs = dt.datetime.fromtimestamp(gap_start / 1000, tz=dt.timezone.utc).date()
        ge = dt.datetime.fromtimestamp(gap_end / 1000, tz=dt.timezone.utc).date()
        log.info("Fetching %s %s..%s from %s", ticker, gs, ge, source)
        rows = provider.fetch_bars(ticker, gs, ge, timespan)
        if rows:
            cache.upsert(rows, timespan=timespan, source=source)

    df = cache.query(ticker, start_ms, end_ms, timespan=timespan, source=source)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("datetime").drop(columns=["timestamp"])
```

- [ ] **Step 4: Run the dispatch test to verify it passes**

Run: `python -m pytest trader/tests/test_loader_dispatch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add trader/data/loader.py trader/tests/test_loader_dispatch.py
git commit -m "feat(trader): source-agnostic cache-aside loader with yahoo default"
```

---

### Task 5: Engine — plumb `source` through `run_backtest`

**Files:**
- Modify: `trader/engine/runner.py:35-52`

- [ ] **Step 1: Add the `source` parameter to `run_backtest`**

In `trader/engine/runner.py`, change the signature (after `timespan: str = "day",`) to add a `source` parameter, and pass it to `load_bars`.

Signature — add the new line:

```python
def run_backtest(
    strategy_cls,
    params: dict,
    tickers: list[str],
    start: date,
    end: date,
    capital: float = 100_000,
    commission: float = 0.00005,   # 0.5 bps
    slippage_perc: float = 0.0001, # 1 bp
    timespan: str = "day",
    source: str = "yahoo",
) -> BacktestResult:
```

Call site — change the `load_bars` line inside the `for ticker in tickers:` loop:

```python
        df = load_bars(ticker, start, end, timespan=timespan, source=source)
```

- [ ] **Step 2: Verify the smoke/engine tests still import and pass**

Run: `python -m pytest trader/tests/ -v --ignore=trader/tests/test_smoke.py`
Expected: PASS (no behavior change; default `source="yahoo"`).

- [ ] **Step 3: Commit**

```bash
git add trader/engine/runner.py
git commit -m "feat(trader): thread source through run_backtest"
```

---

### Task 6: CLI — `--source` flag + cache-list/clear by source

**Files:**
- Modify: `trader/cli.py`

- [ ] **Step 1: Pass `source` from `cmd_fetch`**

In `trader/cli.py`, change the `load_bars` call inside `cmd_fetch`:

```python
        df = load_bars(t, start, end, timespan=args.timespan, source=args.source)
```

- [ ] **Step 2: Pass `source` from `cmd_backtest`**

In `cmd_backtest`, add `source=args.source` to the `run_backtest(...)` call:

```python
    result = run_backtest(
        strategy_cls=strat_cls,
        params=params,
        tickers=tickers,
        start=_parse_date(args.from_),
        end=_parse_date(args.to),
        capital=args.capital,
        source=args.source,
    )
```

- [ ] **Step 3: Pass `source` from `cmd_sweep`**

In `cmd_sweep`, add `source=args.source` to the `run_backtest(...)` call inside the loop:

```python
        result = run_backtest(
            strategy_cls=strat_cls, params=params,
            tickers=list(params["tickers"]),
            start=_parse_date(args.from_), end=_parse_date(args.to),
            capital=args.capital,
            source=args.source,
        )
```

- [ ] **Step 4: Show `source` in `cmd_cache_list`**

In `cmd_cache_list`, include the `source` column in the printed output:

```python
    print(df[["ticker", "source", "min_date", "max_date", "bar_count"]].to_string(index=False))
```

- [ ] **Step 5: Honor optional `--source` in `cmd_cache_clear`**

In `cmd_cache_clear`, pass the (optional) source through:

```python
def cmd_cache_clear(args):
    cache = Cache(CACHE_DB)
    n = cache.clear(args.ticker.upper(), timespan=args.timespan, source=args.source)
    msg = f"deleted {n} rows for {args.ticker.upper()}"
    print(msg if args.source is None else f"{msg} (source={args.source})")
```

- [ ] **Step 6: Register the `--source` arguments in `build_parser`**

Add `--source` to the `fetch`, `backtest`, and `sweep` subparsers, and an optional `--source` to `cache-clear`. Also update the `fetch` help text.

`fetch` parser — change help and add the flag:

```python
    pf = sp.add_parser("fetch", help="Preload cache with bars from Yahoo/Massive")
    pf.add_argument("tickers", help="comma-separated tickers, e.g. AMD,NVDA")
    pf.add_argument("--from", dest="from_", required=True)
    pf.add_argument("--to", default="today")
    pf.add_argument("--timespan", default="day")
    pf.add_argument("--source", choices=["yahoo", "massive"], default="yahoo")
    pf.set_defaults(func=cmd_fetch)
```

`cache-clear` parser — add the optional source:

```python
    pc.add_argument("ticker")
    pc.add_argument("--timespan", default="day")
    pc.add_argument("--source", choices=["yahoo", "massive"], default=None)
    pc.set_defaults(func=cmd_cache_clear)
```

`backtest` parser — add the flag before `_attach_strategy_flags(pb)`:

```python
    pb.add_argument("--out", required=True)
    pb.add_argument("--source", choices=["yahoo", "massive"], default="yahoo")
    _attach_strategy_flags(pb)
    pb.set_defaults(func=cmd_backtest)
```

`sweep` parser — add the flag before `_attach_strategy_flags(psw, allow_csv=True)`:

```python
    psw.add_argument("--out", required=True)
    psw.add_argument("--source", choices=["yahoo", "massive"], default="yahoo")
    _attach_strategy_flags(psw, allow_csv=True)
    psw.set_defaults(func=cmd_sweep)
```

- [ ] **Step 7: Smoke-test the CLI parses and lists**

Run: `python -m trader cache-list`
Expected: prints the cache table (now with a `source` column) or `(empty cache)` — no traceback.

Run: `python -m trader fetch --help`
Expected: help text shows `--source {yahoo,massive}`.

- [ ] **Step 8: Commit**

```bash
git add trader/cli.py
git commit -m "feat(trader): --source flag on fetch/backtest/sweep + cache-list source column"
```

---

### Task 7: Dependency + full-suite verification

**Files:**
- Modify: `trader/requirements.txt`

- [ ] **Step 1: Add yfinance to requirements**

Append to `trader/requirements.txt` (after the `polygon-api-client` line):

```
yfinance>=1.4
```

- [ ] **Step 2: Run the full offline test suite**

Run: `python -m pytest trader/tests/ -v --ignore=trader/tests/test_smoke.py`
Expected: PASS — all existing tests plus the four new test files.

- [ ] **Step 3: Live keyless smoke (network — optional, may be skipped offline)**

Run: `python -m trader fetch AAPL --from 2024-01-02 --to 2024-01-10`
Expected: prints `AAPL: N bars  2024-01-02 → 2024-01-...` with no MASSIVE_KEY required. (If offline, skip this step.)

- [ ] **Step 4: Commit**

```bash
git add trader/requirements.txt
git commit -m "chore(trader): add yfinance dependency"
```

---

## Self-Review notes

- **Spec coverage:** provider abstraction (Task 3), Yahoo default + flag (Tasks 4/6), cache `source` PK + migration (Task 1), lazy `MASSIVE_KEY` (Task 2), CLI flags + cache-list/clear (Task 6), yfinance dep (Task 7), all four spec tests (Tasks 1/3/4). ✓
- **Type consistency:** every `fetch_bars(ticker, start: date, end: date, timespan)` signature matches across `yahoo.py`, `massive.py`, and the `loader` call site; `Cache` methods take `source` consistently; `run_backtest`/`load_bars`/CLI all use the keyword `source`. ✓
- **Backward compatibility:** existing `test_cache.py` untouched and still green because cache methods default `source="massive"`. ✓
```
