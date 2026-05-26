# Trader Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strategy-agnostic Python backtest framework with SQLite-cached market data, auto-registering strategies, generic cointegration pair trading as the first strategy, backtrader event-driven engine, CLI commands, and a 3-level test pyramid. Success: `python -m trader backtest pair_trading --tickers AMD,NVDA ...` produces a complete result folder, and the same command with `--tickers KO,PEP` works without code changes.

**Architecture:** Three independently testable layers under `etoro/trader/`. `data/` knows about SQLite + Massive API and returns DataFrames. `strategies/` consumes DataFrames and emits backtrader signals; new strategies are added by dropping a file (metaclass auto-registers). `engine/` wires backtrader Cerebro + analyzers and writes outputs. The CLI orchestrates. The package reads `MASSIVE_KEY` from `etoro/back/.env` (no duplication of secrets).

**Tech Stack:** Python 3.11+, backtrader (event-driven engine), pandas, statsmodels (ADF cointegration test, OLS hedge ratio), polygon-api-client (Massive REST SDK), SQLite via stdlib `sqlite3`, matplotlib (plots), pytest + pytest-cov.

---

## File map

| Path | Responsibility |
|---|---|
| `trader/requirements.txt` | Python deps |
| `trader/__init__.py` | Package marker, version |
| `trader/__main__.py` | `python -m trader ...` entry — delegates to cli |
| `trader/cli.py` | argparse with subcommands: fetch, cache-list, cache-clear, strategies, backtest, sweep |
| `trader/config.py` | Loads `MASSIVE_KEY` from `etoro/back/.env`; cache path |
| `trader/data/__init__.py` | Re-exports `load_bars` |
| `trader/data/cache.py` | SQLite store: schema bootstrap, upsert, range query |
| `trader/data/loader.py` | Cache-aside: detect gaps → fetch via SDK → upsert → return DataFrame |
| `trader/strategies/__init__.py` | Imports every `.py` under `strategies/` so subclasses register |
| `trader/strategies/base.py` | `BaseStrategy(bt.Strategy)` + metaclass that fills `STRATEGY_REGISTRY` |
| `trader/strategies/pair_trading.py` | Generic 2-ticker cointegration strategy |
| `trader/engine/__init__.py` | Re-exports `run_backtest`, `BacktestResult` |
| `trader/engine/runner.py` | Cerebro wrapper: build feeds, add analyzers, run, collect |
| `trader/engine/analyzers.py` | Sharpe/Sortino/MaxDD/Calmar/WinRate/ProfitFactor extractors |
| `trader/engine/report.py` | Write `result.json`, `trades.csv`, equity/drawdown/z-score PNGs, `run.log` |
| `trader/tests/conftest.py` | Pytest fixtures: temp cache db, sample bars |
| `trader/tests/fixtures/amd_2023.csv` | ~50 days AMD bars for offline tests |
| `trader/tests/fixtures/nvda_2023.csv` | ~50 days NVDA bars for offline tests |
| `trader/tests/test_cache.py` | Cache unit tests |
| `trader/tests/test_loader.py` | Loader unit tests with mocked SDK |
| `trader/tests/test_pair_trading.py` | Strategy logic on synthetic cointegrated series |
| `trader/tests/test_smoke.py` | End-to-end run on fixture data |

---

## Task 1: Project scaffolding

**Files:**
- Create: `etoro/trader/__init__.py`, `etoro/trader/requirements.txt`, `etoro/trader/.gitkeep` (no — use a real file)
- Create: `etoro/trader/config.py`
- Create: `etoro/trader/__main__.py`

- [ ] **Step 1: Create requirements.txt**

`etoro/trader/requirements.txt`:
```
backtrader>=1.9.78
pandas>=2.0
numpy>=1.24
statsmodels>=0.14
polygon-api-client>=1.14
python-dotenv>=1.0
matplotlib>=3.7
pytest>=8.0
pytest-cov>=5.0
```

- [ ] **Step 2: Install deps**

```bash
cd etoro
python -m pip install -r trader/requirements.txt
```
Expected: installs without errors (some warnings about Windows distributions are fine).

- [ ] **Step 3: Create `trader/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create `trader/config.py`**

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

MASSIVE_KEY = os.getenv("MASSIVE_KEY") or os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
if not MASSIVE_KEY:
    raise RuntimeError(f"MASSIVE_KEY missing from {BACK_ENV}")

CACHE_DIR = Path(os.getenv("ETORO_CACHE_DIR", Path.home() / ".etoro"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "cache.db"
```

- [ ] **Step 5: Create `trader/__main__.py`**

```python
from trader.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Smoke-check config loads**

```bash
cd etoro
python -c "from trader.config import MASSIVE_KEY, CACHE_DB; print('key set:', bool(MASSIVE_KEY)); print('db path:', CACHE_DB)"
```
Expected: `key set: True` and a path under `~/.etoro/cache.db`.

- [ ] **Step 7: Commit**

```bash
cd etoro
git add trader/
git commit -m "feat(trader): scaffolding — requirements, config, package init"
```

---

## Task 2: SQLite cache (TDD)

**Files:**
- Create: `etoro/trader/data/__init__.py`, `etoro/trader/data/cache.py`
- Create: `etoro/trader/tests/__init__.py`, `etoro/trader/tests/conftest.py`, `etoro/trader/tests/test_cache.py`

- [ ] **Step 1: Create test scaffolding**

`etoro/trader/tests/__init__.py`: empty file.

`etoro/trader/tests/conftest.py`:
```python
import sqlite3
from pathlib import Path
import pytest


@pytest.fixture
def temp_db(tmp_path: Path):
    """Fresh SQLite path per test."""
    return tmp_path / "cache.db"
```

- [ ] **Step 2: Write first failing test (schema bootstrap)**

`etoro/trader/tests/test_cache.py`:
```python
import sqlite3
import pandas as pd
import pytest

from trader.data.cache import Cache


def test_init_creates_schema(temp_db):
    cache = Cache(temp_db)
    with sqlite3.connect(temp_db) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
    assert "bars" in tables
```

- [ ] **Step 3: Run — verify it fails with ImportError**

```bash
cd etoro
pytest trader/tests/test_cache.py::test_init_creates_schema -v
```
Expected: FAIL with `ModuleNotFoundError: trader.data.cache`.

- [ ] **Step 4: Create empty `data/__init__.py` + minimal `cache.py`**

`etoro/trader/data/__init__.py`: empty file.

`etoro/trader/data/cache.py`:
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
    PRIMARY KEY (ticker, timestamp, timespan)
);
CREATE INDEX IF NOT EXISTS idx_bars_ticker_range
    ON bars(ticker, timespan, timestamp);
"""


class Cache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
```

- [ ] **Step 5: Re-run test — should pass**

```bash
pytest trader/tests/test_cache.py::test_init_creates_schema -v
```
Expected: PASS.

- [ ] **Step 6: Add upsert test (idempotency)**

Append to `test_cache.py`:
```python
def test_upsert_idempotent(temp_db):
    cache = Cache(temp_db)
    bar = {"ticker": "AAPL", "timestamp": 1700000000000,
           "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0,
           "volume": 1_000_000.0, "vwap": 100.5}
    cache.upsert([bar])
    cache.upsert([bar])  # same row twice
    df = cache.query("AAPL", start_ms=0, end_ms=1_800_000_000_000)
    assert len(df) == 1
    assert df.iloc[0]["close"] == 101.0
```

- [ ] **Step 7: Run — verify it fails (upsert + query missing)**

```bash
pytest trader/tests/test_cache.py::test_upsert_idempotent -v
```
Expected: FAIL with `AttributeError: 'Cache' object has no attribute 'upsert'`.

- [ ] **Step 8: Implement upsert + query**

Append to `cache.py` (inside `Cache`):
```python
    def upsert(self, bars: Iterable[dict], timespan: str = "day") -> int:
        rows = [(b["ticker"], int(b["timestamp"]),
                 b.get("open"), b.get("high"), b.get("low"), b.get("close"),
                 b.get("volume"), b.get("vwap"), 1, timespan) for b in bars]
        if not rows:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO bars (ticker, timestamp, open, high, low, close,
                                  volume, vwap, adjusted, timespan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, timestamp, timespan) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, vwap=excluded.vwap
            """, rows)
            return conn.total_changes

    def query(self, ticker: str, start_ms: int, end_ms: int,
              timespan: str = "day") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT timestamp, open, high, low, close, volume, vwap
                   FROM bars
                   WHERE ticker = ? AND timespan = ?
                     AND timestamp BETWEEN ? AND ?
                   ORDER BY timestamp""",
                conn, params=(ticker, timespan, start_ms, end_ms),
            )
```

- [ ] **Step 9: Re-run all cache tests**

```bash
pytest trader/tests/test_cache.py -v
```
Expected: PASS (2 tests).

- [ ] **Step 10: Add coverage gap test (missing data → empty df)**

Append:
```python
def test_query_unknown_ticker_returns_empty(temp_db):
    cache = Cache(temp_db)
    df = cache.query("ZZZZ", 0, 2_000_000_000_000)
    assert df.empty
```
Run:
```bash
pytest trader/tests/test_cache.py -v
```
Expected: 3 PASS.

- [ ] **Step 11: Add coverage_ranges() — what dates do we have?**

Add test:
```python
def test_coverage_ranges_after_insert(temp_db):
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": 1_700_000_000_000,
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "vwap": 1},
        {"ticker": "AAPL", "timestamp": 1_700_086_400_000,
         "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "vwap": 2},
    ])
    coverage = cache.coverage("AAPL")
    assert coverage == (1_700_000_000_000, 1_700_086_400_000)


def test_coverage_unknown_ticker_returns_none(temp_db):
    cache = Cache(temp_db)
    assert cache.coverage("ZZZZ") is None
```

Add to `Cache`:
```python
    def coverage(self, ticker: str, timespan: str = "day") -> tuple[int, int] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM bars "
                "WHERE ticker = ? AND timespan = ?",
                (ticker, timespan),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return (int(row[0]), int(row[1]))

    def clear(self, ticker: str, timespan: str = "day") -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM bars WHERE ticker = ? AND timespan = ?",
                (ticker, timespan),
            )
            return cur.rowcount

    def list_tickers(self, timespan: str = "day") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                "SELECT ticker, MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts, "
                "       COUNT(*) AS bar_count "
                "FROM bars WHERE timespan = ? GROUP BY ticker ORDER BY ticker",
                conn, params=(timespan,),
            )
```

- [ ] **Step 12: Run all cache tests**

```bash
pytest trader/tests/test_cache.py -v --cov=trader/data/cache --cov-report=term-missing
```
Expected: ≥5 PASS, cache.py ≥ 90% coverage.

- [ ] **Step 13: Commit**

```bash
cd etoro
git add trader/data/ trader/tests/__init__.py trader/tests/conftest.py trader/tests/test_cache.py
git commit -m "feat(trader): SQLite cache with upsert/query/coverage/clear"
```

---

## Task 3: Data loader (TDD with mocked SDK)

**Files:**
- Create: `etoro/trader/data/loader.py`
- Modify: `etoro/trader/data/__init__.py` (export `load_bars`)
- Create: `etoro/trader/tests/test_loader.py`

- [ ] **Step 1: Write the failing test (cache-hit avoids API)**

`etoro/trader/tests/test_loader.py`:
```python
from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from trader.data.cache import Cache
from trader.data.loader import load_bars


def _ms(d: date) -> int:
    import datetime as dt
    return int(dt.datetime(d.year, d.month, d.day).timestamp() * 1000)


def test_cache_hit_skips_api(temp_db, monkeypatch):
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 2)),
         "open": 100, "high": 101, "low": 99, "close": 100.5,
         "volume": 1_000_000, "vwap": 100.2},
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 3)),
         "open": 101, "high": 103, "low": 100, "close": 102,
         "volume": 1_200_000, "vwap": 101.8},
    ])
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)
    fake_client = MagicMock()
    with patch("trader.data.loader._client", return_value=fake_client):
        df = load_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3))
    assert len(df) == 2
    assert fake_client.list_aggs.call_count == 0
```

- [ ] **Step 2: Run — verify it fails (loader doesn't exist)**

```bash
pytest trader/tests/test_loader.py::test_cache_hit_skips_api -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement loader**

`etoro/trader/data/loader.py`:
```python
"""Cache-aside loader: SQLite first, fetch missing range from Massive API."""
from __future__ import annotations
import datetime as dt
import logging
from datetime import date
from functools import lru_cache
from typing import Optional
import pandas as pd

from trader.config import CACHE_DB, MASSIVE_KEY
from trader.data.cache import Cache

log = logging.getLogger(__name__)

try:
    from massive import RESTClient
except ImportError:
    from polygon import RESTClient


@lru_cache(maxsize=1)
def _client() -> RESTClient:
    return RESTClient(api_key=MASSIVE_KEY)


def _to_ms(d: date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _gaps(coverage: Optional[tuple[int, int]], start_ms: int, end_ms: int) -> list[tuple[int, int]]:
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
              timespan: str = "day") -> pd.DataFrame:
    """Cache-aside fetch. Returns DataFrame indexed by datetime (UTC)."""
    cache = Cache(CACHE_DB)
    start_ms, end_ms = _to_ms(start), _to_ms(end)

    coverage = cache.coverage(ticker, timespan)
    gaps = _gaps(coverage, start_ms, end_ms)

    for gap_start, gap_end in gaps:
        log.info("Fetching %s %s..%s from Massive", ticker, gap_start, gap_end)
        bars = list(_client().list_aggs(
            ticker, 1, timespan,
            dt.datetime.fromtimestamp(gap_start / 1000, tz=dt.timezone.utc).date().isoformat(),
            dt.datetime.fromtimestamp(gap_end / 1000, tz=dt.timezone.utc).date().isoformat(),
            limit=50000,
        ))
        rows = [{"ticker": ticker, "timestamp": b.timestamp,
                 "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                 "volume": b.volume, "vwap": getattr(b, "vwap", None)} for b in bars]
        if rows:
            cache.upsert(rows, timespan=timespan)

    df = cache.query(ticker, start_ms, end_ms, timespan=timespan)
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("datetime").drop(columns=["timestamp"])
```

- [ ] **Step 4: Export `load_bars`**

`etoro/trader/data/__init__.py`:
```python
from trader.data.loader import load_bars

__all__ = ["load_bars"]
```

- [ ] **Step 5: Re-run test**

```bash
pytest trader/tests/test_loader.py::test_cache_hit_skips_api -v
```
Expected: PASS.

- [ ] **Step 6: Add partial-gap test**

Append to `test_loader.py`:
```python
def test_partial_gap_fetches_delta_only(temp_db, monkeypatch):
    """Cache has Jan 2024. Request Jan 2023..Feb 2024 — must fetch only the missing left+right slices."""
    cache = Cache(temp_db)
    cache.upsert([
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 2)),
         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "vwap": 1},
        {"ticker": "AAPL", "timestamp": _ms(date(2024, 1, 31)),
         "open": 2, "high": 2, "low": 2, "close": 2, "volume": 1, "vwap": 2},
    ])
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)

    fake_client = MagicMock()
    fake_client.list_aggs.return_value = iter([])  # no new bars returned
    with patch("trader.data.loader._client", return_value=fake_client):
        load_bars("AAPL", date(2023, 1, 1), date(2024, 2, 28))

    # Two API calls: left gap (2023-01-01..2024-01-01) + right gap (2024-02-01..2024-02-28)
    assert fake_client.list_aggs.call_count == 2


def test_unknown_ticker_returns_empty(temp_db, monkeypatch):
    monkeypatch.setattr("trader.data.loader.CACHE_DB", temp_db)
    fake_client = MagicMock()
    fake_client.list_aggs.return_value = iter([])
    with patch("trader.data.loader._client", return_value=fake_client):
        df = load_bars("ZZZZ", date(2024, 1, 1), date(2024, 1, 5))
    assert df.empty
```

- [ ] **Step 7: Run all loader tests**

```bash
pytest trader/tests/test_loader.py -v
```
Expected: 3 PASS.

- [ ] **Step 8: Commit**

```bash
cd etoro
git add trader/data/__init__.py trader/data/loader.py trader/tests/test_loader.py
git commit -m "feat(trader): cache-aside loader with gap detection"
```

---

## Task 4: Strategy base + auto-registry (TDD)

**Files:**
- Create: `etoro/trader/strategies/__init__.py`
- Create: `etoro/trader/strategies/base.py`
- Create: `etoro/trader/tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

`etoro/trader/tests/test_registry.py`:
```python
import backtrader as bt
import pytest

from trader.strategies.base import BaseStrategy, STRATEGY_REGISTRY


def test_subclass_auto_registers():
    """Defining a BaseStrategy subclass with a `name` attr registers it."""
    initial = set(STRATEGY_REGISTRY)

    class DummyStrategy(BaseStrategy):
        name = "dummy_test_strat"
        description = "Test strategy"

        from dataclasses import dataclass

        @dataclass
        class _P:
            window: int = 5

        params_dataclass = _P

    assert "dummy_test_strat" in STRATEGY_REGISTRY
    assert STRATEGY_REGISTRY["dummy_test_strat"] is DummyStrategy
    # Cleanup so test is rerunnable
    STRATEGY_REGISTRY.pop("dummy_test_strat", None)
```

- [ ] **Step 2: Run — verify it fails**

```bash
pytest trader/tests/test_registry.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement base + metaclass**

`etoro/trader/strategies/base.py`:
```python
"""Strategy ABC + auto-registry.

Defining a class that inherits from BaseStrategy and sets `name` adds it to
STRATEGY_REGISTRY without manual edits. The CLI discovers strategies this way.
"""
from __future__ import annotations
from typing import ClassVar
import backtrader as bt

STRATEGY_REGISTRY: dict[str, type] = {}


class _AutoRegisterMeta(type(bt.Strategy)):
    def __init__(cls, name_attr, bases, namespace, **kwargs):
        super().__init__(name_attr, bases, namespace, **kwargs)
        cls_name = namespace.get("name")
        if cls_name and name_attr != "BaseStrategy":
            STRATEGY_REGISTRY[cls_name] = cls


class BaseStrategy(bt.Strategy, metaclass=_AutoRegisterMeta):
    """Subclass this, set `name` + `description` + `params_dataclass`."""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    params_dataclass: ClassVar[type] = type(None)

    def __init__(self):
        self._trade_log: list[dict] = []

    def log_trade(self, side: str, ticker: str, size: float, price: float, reason: str):
        self._trade_log.append({
            "datetime": self.datas[0].datetime.datetime(0).isoformat(),
            "side": side, "ticker": ticker, "size": size,
            "price": price, "reason": reason,
        })

    @classmethod
    def required_tickers(cls, params) -> list[str] | None:
        """Override if strategy hardcodes a universe; else return None."""
        return None
```

- [ ] **Step 4: Make strategies importable as a package**

`etoro/trader/strategies/__init__.py`:
```python
"""Auto-import every strategy module so subclasses register on import."""
import importlib
import pkgutil

from trader.strategies.base import BaseStrategy, STRATEGY_REGISTRY  # noqa: F401

# Walk this package and import each module so its BaseStrategy subclass registers.
for _info in pkgutil.iter_modules(__path__):
    if _info.name not in ("base", "__init__"):
        importlib.import_module(f"{__name__}.{_info.name}")
```

- [ ] **Step 5: Re-run test**

```bash
pytest trader/tests/test_registry.py -v
```
Expected: PASS.

- [ ] **Step 6: Add log_trade test**

Append to `test_registry.py`:
```python
def test_log_trade_appends_entry(monkeypatch):
    """Verify log_trade appends to internal list."""
    class _Strat(BaseStrategy):
        name = "log_trade_test"
        description = "x"
        params_dataclass = type("P", (), {})

    s = _Strat.__new__(_Strat)
    s._trade_log = []
    # backtrader's data feed datetime call — fake it
    s.datas = [type("D", (), {"datetime": type("DT", (), {"datetime": lambda self, offset: __import__("datetime").datetime(2024, 1, 1)})()})()]
    s.log_trade("LONG", "AAPL", 10, 100.5, "entry signal")
    assert len(s._trade_log) == 1
    assert s._trade_log[0]["ticker"] == "AAPL"
    STRATEGY_REGISTRY.pop("log_trade_test", None)
```

- [ ] **Step 7: Run tests**

```bash
pytest trader/tests/test_registry.py -v
```
Expected: 2 PASS.

- [ ] **Step 8: Commit**

```bash
cd etoro
git add trader/strategies/ trader/tests/test_registry.py
git commit -m "feat(trader): BaseStrategy + auto-registry metaclass"
```

---

## Task 5: Pair trading strategy (TDD on synthetic data)

**Files:**
- Create: `etoro/trader/strategies/pair_trading.py`
- Create: `etoro/trader/tests/test_pair_trading.py`

- [ ] **Step 1: Write the failing test (cointegration detection)**

`etoro/trader/tests/test_pair_trading.py`:
```python
"""Synthetic-series tests: verify pair_trading triggers correctly on known patterns.

Strategy is tested at the math layer (hedge ratio, z-score, signal decisions)
not through the full Cerebro to keep tests fast and deterministic.
"""
from dataclasses import asdict
import numpy as np
import pandas as pd
import pytest

from trader.strategies.pair_trading import (
    PairTradingStrategy,
    PairParams,
    compute_hedge_ratio,
    compute_zscore,
    cointegration_pvalue,
)


def _cointegrated_pair(n: int = 300, beta: float = 2.0, seed: int = 42):
    rng = np.random.default_rng(seed)
    amd = np.cumsum(rng.normal(0, 1, n)) + 100
    noise = rng.normal(0, 0.5, n)
    nvda = beta * amd + 10 + noise
    return pd.Series(amd, name="AMD"), pd.Series(nvda, name="NVDA")


def test_hedge_ratio_recovers_known_beta():
    amd, nvda = _cointegrated_pair(beta=2.0)
    beta = compute_hedge_ratio(nvda.tail(120), amd.tail(120))
    assert 1.85 < beta < 2.15  # tight tolerance — synthetic + 0.5σ noise


def test_cointegration_pvalue_low_for_cointegrated():
    amd, nvda = _cointegrated_pair()
    spread = nvda - 2.0 * amd
    p = cointegration_pvalue(spread.tail(120).to_numpy())
    assert p < 0.05


def test_cointegration_pvalue_high_for_random_walks():
    rng = np.random.default_rng(7)
    a = pd.Series(np.cumsum(rng.normal(0, 1, 300)))
    b = pd.Series(np.cumsum(rng.normal(0, 1, 300)))
    spread = b - 1.0 * a
    p = cointegration_pvalue(spread.tail(120).to_numpy())
    # Independent random walks should generally not be cointegrated
    assert p > 0.05
```

- [ ] **Step 2: Run — verify it fails**

```bash
pytest trader/tests/test_pair_trading.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement helpers + strategy skeleton**

`etoro/trader/strategies/pair_trading.py`:
```python
"""Generic cointegration pair trading. Works on ANY 2 tickers.

Pattern:
    1. Rolling OLS hedge ratio β: y_t = α + β·x_t + ε_t
    2. Spread = y - β·x
    3. z-score on spread over lookback
    4. ADF test on spread; only trade when p < min_p_value
    5. Enter when |z| > entry_z, exit when |z| < exit_z, stop when |z| > stop_loss_z
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar

import backtrader as bt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

from trader.strategies.base import BaseStrategy


@dataclass
class PairParams:
    tickers: tuple[str, str] = ("AMD", "NVDA")
    lookback: int = 60
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_loss_z: float = 3.5
    capital_per_leg: float = 50_000
    min_p_value: float = 0.05


def compute_hedge_ratio(y: pd.Series, x: pd.Series) -> float:
    """OLS slope: y = α + β·x. Returns β."""
    X = sm.add_constant(x.to_numpy())
    model = sm.OLS(y.to_numpy(), X).fit()
    return float(model.params[1])


def compute_zscore(spread: pd.Series) -> float:
    """Standardize the last value of `spread` against its own mean/std."""
    mu = spread.mean()
    sigma = spread.std(ddof=0)
    if sigma == 0 or np.isnan(sigma):
        return 0.0
    return float((spread.iloc[-1] - mu) / sigma)


def cointegration_pvalue(spread: np.ndarray) -> float:
    """ADF p-value on the spread."""
    if len(spread) < 20:
        return 1.0
    try:
        result = adfuller(spread, autolag="AIC")
        return float(result[1])
    except (ValueError, np.linalg.LinAlgError):
        return 1.0


class PairTradingStrategy(BaseStrategy):
    """Generic 2-ticker cointegration pair trading."""
    name = "pair_trading"
    description = "Generic cointegration pair trading (any 2 tickers)"
    params_dataclass = PairParams

    params = (
        ("lookback", 60),
        ("entry_z", 2.0),
        ("exit_z", 0.5),
        ("stop_loss_z", 3.5),
        ("capital_per_leg", 50_000),
        ("min_p_value", 0.05),
    )

    def __init__(self):
        super().__init__()
        if len(self.datas) != 2:
            raise ValueError("pair_trading requires exactly 2 data feeds")
        self.y = self.datas[0]   # treated as y in OLS
        self.x = self.datas[1]   # treated as x in OLS
        self._position_state = "flat"  # flat | long_y_short_x | short_y_long_x

    @classmethod
    def required_tickers(cls, params: PairParams) -> list[str]:
        return list(params.tickers)

    def _recent_series(self, data, n: int) -> pd.Series:
        return pd.Series([data[-i] for i in range(n - 1, -1, -1)])

    def next(self):
        if len(self.y) < self.p.lookback or len(self.x) < self.p.lookback:
            return

        y_window = self._recent_series(self.y, self.p.lookback)
        x_window = self._recent_series(self.x, self.p.lookback)
        beta = compute_hedge_ratio(y_window, x_window)
        spread = y_window - beta * x_window
        z = compute_zscore(spread)
        p_value = cointegration_pvalue(spread.to_numpy())

        y_name = self.y._name
        x_name = self.x._name

        # Stop-loss check first (regardless of cointegration)
        if self._position_state != "flat" and abs(z) > self.p.stop_loss_z:
            self.close(data=self.y)
            self.close(data=self.x)
            self.log_trade("EXIT", y_name, 0, self.y[0], f"stop_loss z={z:.2f}")
            self.log_trade("EXIT", x_name, 0, self.x[0], f"stop_loss z={z:.2f}")
            self._position_state = "flat"
            return

        # Cointegration filter (no new entries if not cointegrated)
        if self._position_state == "flat" and p_value > self.p.min_p_value:
            return

        # Sizing: equal dollar
        size_y = self.p.capital_per_leg / self.y[0]
        size_x = self.p.capital_per_leg / self.x[0]

        if self._position_state == "flat":
            if z > self.p.entry_z:
                # Spread too high → short y, long x
                self.sell(data=self.y, size=size_y)
                self.buy(data=self.x, size=size_x * beta)
                self.log_trade("SHORT", y_name, size_y, self.y[0], f"entry z={z:.2f}")
                self.log_trade("LONG", x_name, size_x * beta, self.x[0], f"entry z={z:.2f}")
                self._position_state = "short_y_long_x"
            elif z < -self.p.entry_z:
                self.buy(data=self.y, size=size_y)
                self.sell(data=self.x, size=size_x * beta)
                self.log_trade("LONG", y_name, size_y, self.y[0], f"entry z={z:.2f}")
                self.log_trade("SHORT", x_name, size_x * beta, self.x[0], f"entry z={z:.2f}")
                self._position_state = "long_y_short_x"
        else:
            # In position — check exit
            if abs(z) < self.p.exit_z:
                self.close(data=self.y)
                self.close(data=self.x)
                self.log_trade("EXIT", y_name, 0, self.y[0], f"mean reverted z={z:.2f}")
                self.log_trade("EXIT", x_name, 0, self.x[0], f"mean reverted z={z:.2f}")
                self._position_state = "flat"
```

- [ ] **Step 4: Re-run tests**

```bash
pytest trader/tests/test_pair_trading.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
cd etoro
git add trader/strategies/pair_trading.py trader/tests/test_pair_trading.py
git commit -m "feat(trader): generic pair-trading strategy + math helpers"
```

---

## Task 6: Engine runner + analyzers

**Files:**
- Create: `etoro/trader/engine/__init__.py`, `etoro/trader/engine/runner.py`, `etoro/trader/engine/analyzers.py`

- [ ] **Step 1: Create analyzers module**

`etoro/trader/engine/analyzers.py`:
```python
"""Metric extractors that translate backtrader Analyzers to flat dicts."""
from __future__ import annotations
from typing import Any

import backtrader as bt


def attach_default_analyzers(cerebro: bt.Cerebro) -> None:
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.04, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.SortinoRatio, _name="sortino", riskfreerate=0.04)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days)


def extract_metrics(strat: bt.Strategy) -> dict[str, Any]:
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio")
    sortino = strat.analyzers.sortino.get_analysis().get("sortinoratio")
    dd = strat.analyzers.dd.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    total_trades = trades.get("total", {}).get("closed", 0)
    won = trades.get("won", {}).get("total", 0)
    lost = trades.get("lost", {}).get("total", 0)
    pnl_won = trades.get("won", {}).get("pnl", {}).get("total", 0.0)
    pnl_lost = abs(trades.get("lost", {}).get("pnl", {}).get("total", 0.0))

    win_rate = (won / total_trades) if total_trades else 0.0
    profit_factor = (pnl_won / pnl_lost) if pnl_lost else float("inf") if pnl_won else 0.0

    max_dd = dd.get("max", {}).get("drawdown", 0.0) / 100.0  # percent → fraction
    cagr = returns.get("rnorm", 0.0)
    total_return = returns.get("rtot", 0.0)
    calmar = (cagr / abs(max_dd)) if max_dd else 0.0

    avg_len = trades.get("len", {}).get("average", 0)

    return {
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "sharpe": round(sharpe, 4) if sharpe else None,
        "sortino": round(sortino, 4) if sortino else None,
        "max_drawdown": -round(abs(max_dd), 6),
        "calmar": round(calmar, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "total_trades": int(total_trades),
        "avg_trade_days": float(avg_len),
    }


def extract_equity_curve(strat: bt.Strategy):
    """Return pd.Series of daily portfolio value (broker value)."""
    import pandas as pd
    timereturn = strat.analyzers.timereturn.get_analysis()
    if not timereturn:
        return pd.Series(dtype=float)
    return pd.Series(timereturn).sort_index()
```

- [ ] **Step 2: Create runner module**

`etoro/trader/engine/__init__.py`:
```python
from trader.engine.runner import run_backtest, BacktestResult

__all__ = ["run_backtest", "BacktestResult"]
```

`etoro/trader/engine/runner.py`:
```python
"""Backtest orchestration: data feeds → Cerebro → analyzers → result."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Any
import pandas as pd
import backtrader as bt

from trader.data import load_bars
from trader.engine.analyzers import attach_default_analyzers, extract_metrics, extract_equity_curve


@dataclass
class BacktestResult:
    strategy: str
    params: dict
    tickers: list[str]
    period: tuple[date, date]
    capital: float
    metrics: dict[str, Any]
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    trade_log: list[dict] = field(default_factory=list)


def _bars_to_feed(df: pd.DataFrame, name: str) -> bt.feeds.PandasData:
    """Convert our DataFrame to a backtrader PandasData feed."""
    bt_df = df.rename(columns={"open": "open", "high": "high", "low": "low",
                                "close": "close", "volume": "volume"}).copy()
    bt_df.index = bt_df.index.tz_convert(None) if bt_df.index.tz else bt_df.index
    return bt.feeds.PandasData(dataname=bt_df, name=name,
                                open="open", high="high", low="low",
                                close="close", volume="volume", openinterest=None)


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
) -> BacktestResult:
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=commission)
    cerebro.broker.set_slippage_perc(perc=slippage_perc)

    for ticker in tickers:
        df = load_bars(ticker, start, end, timespan=timespan)
        if df.empty:
            raise RuntimeError(f"No bars for {ticker} in [{start}, {end}]")
        cerebro.adddata(_bars_to_feed(df, ticker))

    bt_params = {k: v for k, v in params.items()
                 if k in {p[0] for p in strategy_cls.params}}
    cerebro.addstrategy(strategy_cls, **bt_params)
    attach_default_analyzers(cerebro)

    results = cerebro.run()
    strat = results[0]

    return BacktestResult(
        strategy=strategy_cls.name,
        params=params,
        tickers=tickers,
        period=(start, end),
        capital=capital,
        metrics=extract_metrics(strat),
        equity_curve=extract_equity_curve(strat),
        trade_log=strat._trade_log,
    )
```

- [ ] **Step 3: Quick smoke (no test file yet — sanity check imports)**

```bash
cd etoro
python -c "from trader.engine import run_backtest, BacktestResult; print('engine ok')"
```
Expected: `engine ok`.

- [ ] **Step 4: Commit**

```bash
cd etoro
git add trader/engine/
git commit -m "feat(trader): backtrader-based runner + default analyzers"
```

---

## Task 7: Report writer (JSON + CSV + PNG)

**Files:**
- Create: `etoro/trader/engine/report.py`

- [ ] **Step 1: Implement report writer**

`etoro/trader/engine/report.py`:
```python
"""Write a BacktestResult to an output folder (JSON + CSV + PNGs)."""
from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # no GUI
import matplotlib.pyplot as plt

from trader.engine.runner import BacktestResult


def write_report(result: BacktestResult, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. result.json
    payload = {
        "strategy": result.strategy,
        "params": _jsonable(result.params),
        "tickers": result.tickers,
        "period": [result.period[0].isoformat(), result.period[1].isoformat()],
        "capital": result.capital,
        "metrics": result.metrics,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "result.json").write_text(json.dumps(payload, indent=2, default=str))

    # 2. trades.csv
    trades_df = pd.DataFrame(result.trade_log)
    trades_df.to_csv(out / "trades.csv", index=False)

    # 3. equity_curve.png
    if not result.equity_curve.empty:
        eq = (1 + result.equity_curve).cumprod() * result.capital
        plt.figure(figsize=(10, 5))
        eq.plot(title=f"Equity Curve — {result.strategy} {result.tickers}")
        plt.ylabel("Portfolio Value")
        plt.tight_layout()
        plt.savefig(out / "equity_curve.png", dpi=120)
        plt.close()

        # 4. drawdown.png
        roll_max = eq.cummax()
        dd = (eq - roll_max) / roll_max
        plt.figure(figsize=(10, 4))
        dd.plot(title="Drawdown", color="red")
        plt.fill_between(dd.index, dd.values, 0, color="red", alpha=0.3)
        plt.ylabel("Drawdown")
        plt.tight_layout()
        plt.savefig(out / "drawdown.png", dpi=120)
        plt.close()

    return out


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj
```

- [ ] **Step 2: Update `engine/__init__.py`**

```python
from trader.engine.runner import run_backtest, BacktestResult
from trader.engine.report import write_report

__all__ = ["run_backtest", "BacktestResult", "write_report"]
```

- [ ] **Step 3: Smoke check**

```bash
python -c "from trader.engine import write_report; print('report ok')"
```
Expected: `report ok`.

- [ ] **Step 4: Commit**

```bash
cd etoro
git add trader/engine/report.py trader/engine/__init__.py
git commit -m "feat(trader): JSON+CSV+PNG report writer"
```

---

## Task 8: CLI commands

**Files:**
- Create: `etoro/trader/cli.py`

- [ ] **Step 1: Implement CLI with all subcommands**

`etoro/trader/cli.py`:
```python
"""CLI: python -m trader {fetch | cache-list | cache-clear | strategies | backtest | sweep}."""
from __future__ import annotations
import argparse
import dataclasses
import itertools
import json
import sys
from dataclasses import fields
from datetime import date, datetime
from pathlib import Path

from trader.config import CACHE_DB
from trader.data.cache import Cache
from trader.data.loader import load_bars
from trader.strategies import STRATEGY_REGISTRY  # triggers auto-import


def _parse_date(s: str) -> date:
    if s.lower() == "today":
        return date.today()
    return datetime.fromisoformat(s).date()


def _add_strategy_params(parser, strategy_cls):
    """Derive --flags from a strategy's params_dataclass."""
    dc = strategy_cls.params_dataclass
    for f in fields(dc):
        flag = "--" + f.name.replace("_", "-")
        if f.type is int or f.type == "int":
            parser.add_argument(flag, type=int, default=f.default)
        elif f.type is float or f.type == "float":
            parser.add_argument(flag, type=float, default=f.default)
        elif f.name == "tickers":
            # Handled by top-level --tickers
            continue
        else:
            parser.add_argument(flag, type=str, default=f.default)


def cmd_fetch(args):
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    start = _parse_date(args.from_)
    end = _parse_date(args.to)
    for t in tickers:
        df = load_bars(t, start, end, timespan=args.timespan)
        print(f"{t}: {len(df)} bars  {df.index.min() if not df.empty else '—'} → {df.index.max() if not df.empty else '—'}")


def cmd_cache_list(args):
    cache = Cache(CACHE_DB)
    df = cache.list_tickers(timespan=args.timespan)
    if df.empty:
        print("(empty cache)")
        return
    import pandas as pd
    df["min_date"] = pd.to_datetime(df["min_ts"], unit="ms").dt.date
    df["max_date"] = pd.to_datetime(df["max_ts"], unit="ms").dt.date
    print(df[["ticker", "min_date", "max_date", "bar_count"]].to_string(index=False))


def cmd_cache_clear(args):
    cache = Cache(CACHE_DB)
    n = cache.clear(args.ticker.upper(), timespan=args.timespan)
    print(f"deleted {n} rows for {args.ticker.upper()}")


def cmd_strategies(args):
    if not STRATEGY_REGISTRY:
        print("(no strategies registered)")
        return
    width = max(len(n) for n in STRATEGY_REGISTRY) + 2
    for name, cls in sorted(STRATEGY_REGISTRY.items()):
        print(f"{name:<{width}} {cls.description}")


def cmd_backtest(args):
    from trader.engine import run_backtest, write_report

    strat_cls = STRATEGY_REGISTRY.get(args.strategy)
    if not strat_cls:
        print(f"unknown strategy: {args.strategy}", file=sys.stderr)
        print("Available:", ", ".join(STRATEGY_REGISTRY), file=sys.stderr)
        sys.exit(2)

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    params = {f.name: getattr(args, f.name.replace("-", "_"), f.default)
              for f in fields(strat_cls.params_dataclass)
              if f.name != "tickers"}
    params["tickers"] = tuple(tickers)

    result = run_backtest(
        strategy_cls=strat_cls,
        params=params,
        tickers=tickers,
        start=_parse_date(args.from_),
        end=_parse_date(args.to),
        capital=args.capital,
    )
    out = write_report(result, args.out)
    print(f"\nResults written to {out}")
    print(json.dumps(result.metrics, indent=2))


def cmd_sweep(args):
    """Grid search over comma-separated parameter values."""
    from trader.engine import run_backtest, write_report

    strat_cls = STRATEGY_REGISTRY.get(args.strategy)
    if not strat_cls:
        sys.exit(f"unknown strategy: {args.strategy}")

    grid = {}
    for f in fields(strat_cls.params_dataclass):
        if f.name == "tickers":
            continue
        val = getattr(args, f.name.replace("-", "_"), None)
        if isinstance(val, str) and "," in val:
            cast = int if f.type is int or f.type == "int" else float
            grid[f.name] = [cast(x) for x in val.split(",")]
        elif val is not None:
            grid[f.name] = [val]

    keys = list(grid)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for combo in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        params["tickers"] = tuple(t.strip().upper() for t in args.tickers.split(","))
        slug = "_".join(f"{k}{v}" for k, v in zip(keys, combo))
        result = run_backtest(
            strategy_cls=strat_cls, params=params,
            tickers=list(params["tickers"]),
            start=_parse_date(args.from_), end=_parse_date(args.to),
            capital=args.capital,
        )
        write_report(result, out_dir / slug)
        summary.append({"params": params, "metrics": result.metrics})
        print(f"  {slug}  sharpe={result.metrics.get('sharpe')}  trades={result.metrics.get('total_trades')}")

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n{len(summary)} runs written to {out_dir}")


def build_parser():
    p = argparse.ArgumentParser(prog="trader")
    sp = p.add_subparsers(dest="cmd", required=True)

    pf = sp.add_parser("fetch", help="Preload cache with bars from Massive")
    pf.add_argument("tickers", help="comma-separated tickers, e.g. AMD,NVDA")
    pf.add_argument("--from", dest="from_", required=True)
    pf.add_argument("--to", default="today")
    pf.add_argument("--timespan", default="day")
    pf.set_defaults(func=cmd_fetch)

    pl = sp.add_parser("cache-list", help="Show what's in the cache")
    pl.add_argument("--timespan", default="day")
    pl.set_defaults(func=cmd_cache_list)

    pc = sp.add_parser("cache-clear", help="Delete bars for one ticker")
    pc.add_argument("ticker")
    pc.add_argument("--timespan", default="day")
    pc.set_defaults(func=cmd_cache_clear)

    ps = sp.add_parser("strategies", help="List registered strategies")
    ps.set_defaults(func=cmd_strategies)

    pb = sp.add_parser("backtest", help="Run one backtest config")
    pb.add_argument("strategy")
    pb.add_argument("--tickers", required=True)
    pb.add_argument("--from", dest="from_", required=True)
    pb.add_argument("--to", required=True)
    pb.add_argument("--capital", type=float, default=100_000)
    pb.add_argument("--out", required=True)
    _attach_strategy_flags(pb)
    pb.set_defaults(func=cmd_backtest)

    psw = sp.add_parser("sweep", help="Grid-search a strategy")
    psw.add_argument("strategy")
    psw.add_argument("--tickers", required=True)
    psw.add_argument("--from", dest="from_", required=True)
    psw.add_argument("--to", required=True)
    psw.add_argument("--capital", type=float, default=100_000)
    psw.add_argument("--out", required=True)
    _attach_strategy_flags(psw, allow_csv=True)
    psw.set_defaults(func=cmd_sweep)

    return p


def _attach_strategy_flags(subparser, allow_csv: bool = False):
    """Add per-strategy flags by inspecting each registered dataclass.

    `allow_csv=True` keeps types as str so the sweep command can pass comma lists.
    """
    seen = set()
    for cls in STRATEGY_REGISTRY.values():
        for f in fields(cls.params_dataclass):
            if f.name in seen or f.name == "tickers":
                continue
            seen.add(f.name)
            flag = "--" + f.name.replace("_", "-")
            if allow_csv:
                subparser.add_argument(flag, type=str, default=str(f.default))
            elif f.type is int or f.type == "int":
                subparser.add_argument(flag, type=int, default=f.default)
            elif f.type is float or f.type == "float":
                subparser.add_argument(flag, type=float, default=f.default)
            else:
                subparser.add_argument(flag, type=str, default=f.default)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Sanity check — list strategies**

```bash
cd etoro
python -m trader strategies
```
Expected: prints `pair_trading   Generic cointegration pair trading (any 2 tickers)`.

- [ ] **Step 3: Sanity check — help text**

```bash
python -m trader backtest --help
```
Expected: shows `--tickers`, `--from`, `--to`, `--capital`, `--out`, plus all PairParams flags (`--lookback`, `--entry-z`, `--exit-z`, `--stop-loss-z`, `--capital-per-leg`, `--min-p-value`).

- [ ] **Step 4: Commit**

```bash
cd etoro
git add trader/cli.py
git commit -m "feat(trader): CLI — fetch, cache-list, cache-clear, strategies, backtest, sweep"
```

---

## Task 9: End-to-end smoke test with fixture data

**Files:**
- Create: `etoro/trader/tests/fixtures/amd_2023.csv`, `etoro/trader/tests/fixtures/nvda_2023.csv`
- Create: `etoro/trader/tests/test_smoke.py`

- [ ] **Step 1: Generate fixture data**

```bash
cd etoro
python -c "
from datetime import date, timedelta
import csv, random
random.seed(7)
def write(ticker, base):
    path = f'trader/tests/fixtures/{ticker.lower()}_2023.csv'
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['timestamp','open','high','low','close','volume','vwap'])
        d = date(2023, 1, 3)
        price = base
        for _ in range(120):
            o = price
            h = o * (1 + abs(random.gauss(0, 0.012)))
            l = o * (1 - abs(random.gauss(0, 0.012)))
            c = o + random.gauss(0, o * 0.015)
            ts = int(__import__('datetime').datetime(d.year, d.month, d.day).timestamp() * 1000)
            w.writerow([ts, round(o,2), round(h,2), round(l,2), round(c,2), 1_000_000, round((o+h+l+c)/4,2)])
            price = c
            d = d + timedelta(days=1)
            while d.weekday() >= 5:
                d = d + timedelta(days=1)
write('AMD', 70.0)
write('NVDA', 140.0)
print('fixtures written')
"
```
Expected: writes two CSVs.

- [ ] **Step 2: Write the smoke test**

`etoro/trader/tests/test_smoke.py`:
```python
"""End-to-end: load fixture bars into cache → run pair_trading backtest → verify outputs."""
import csv
import json
import shutil
from datetime import date
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest

from trader.data.cache import Cache


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(ticker: str, cache: Cache):
    path = FIXTURE_DIR / f"{ticker.lower()}_2023.csv"
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append({
                "ticker": ticker,
                "timestamp": int(row["timestamp"]),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"]), "vwap": float(row["vwap"]),
            })
    cache.upsert(rows)


def test_full_backtest_pipeline(tmp_path, monkeypatch):
    """Same fixtures, two ticker pairs would prove ticker-agnosticism. Here: AMD/NVDA."""
    db = tmp_path / "cache.db"
    monkeypatch.setattr("trader.data.loader.CACHE_DB", db)
    monkeypatch.setattr("trader.config.CACHE_DB", db)
    cache = Cache(db)
    _load_fixture("AMD", cache)
    _load_fixture("NVDA", cache)

    from trader.engine import run_backtest, write_report
    from trader.strategies.pair_trading import PairTradingStrategy

    params = {
        "tickers": ("AMD", "NVDA"),
        "lookback": 30,
        "entry_z": 1.5,
        "exit_z": 0.5,
        "stop_loss_z": 3.5,
        "capital_per_leg": 25_000,
        "min_p_value": 0.20,   # loose for short fixture sample
    }
    result = run_backtest(
        strategy_cls=PairTradingStrategy,
        params=params,
        tickers=["AMD", "NVDA"],
        start=date(2023, 1, 3),
        end=date(2023, 7, 1),
        capital=100_000,
    )

    out = write_report(result, tmp_path / "out")
    assert (out / "result.json").exists()
    payload = json.loads((out / "result.json").read_text())
    assert payload["strategy"] == "pair_trading"
    assert set(payload["metrics"].keys()) >= {
        "total_return", "sharpe", "sortino", "max_drawdown",
        "win_rate", "total_trades", "profit_factor",
    }
    assert (out / "trades.csv").exists()
```

- [ ] **Step 3: Run smoke test**

```bash
cd etoro
pytest trader/tests/test_smoke.py -v
```
Expected: PASS. (If `result.json` keys differ slightly, fix in `analyzers.py` before continuing.)

- [ ] **Step 4: Run the full suite + coverage**

```bash
pytest trader/tests/ -v --cov=trader --cov-report=term-missing
```
Expected: all PASS, coverage on `trader/data/` and `trader/strategies/` ≥ 80%.

- [ ] **Step 5: Commit**

```bash
cd etoro
git add trader/tests/fixtures/ trader/tests/test_smoke.py
git commit -m "test(trader): end-to-end smoke + AMD/NVDA fixture bars"
```

---

## Task 10: Live API verification (one real run)

**Files:** none — runs CLI against real Massive API to prove integration.

- [ ] **Step 1: Preload cache for AMD and NVDA**

```bash
cd etoro
python -m trader fetch AMD,NVDA --from 2020-01-01 --to today
```
Expected: prints two lines like `AMD: 1500 bars  2020-01-02 → 2026-05-27`.

- [ ] **Step 2: Verify cache contents**

```bash
python -m trader cache-list
```
Expected: shows AMD + NVDA with date ranges and bar counts.

- [ ] **Step 3: Run pair backtest on AMD/NVDA**

```bash
python -m trader backtest pair_trading \
    --tickers AMD,NVDA \
    --from 2020-01-01 --to 2026-05-01 \
    --capital 100000 \
    --lookback 60 --entry-z 2.0 --exit-z 0.5 \
    --out results/pair_amd_nvda_2020-2026
```
Expected: writes `results/pair_amd_nvda_2020-2026/{result.json, trades.csv, equity_curve.png, drawdown.png}`. Prints metrics JSON to stdout.

- [ ] **Step 4: Run the SAME strategy on a different pair (proves ticker-agnosticism)**

```bash
python -m trader backtest pair_trading \
    --tickers KO,PEP \
    --from 2018-01-01 --to 2026-05-01 \
    --out results/pair_ko_pep_2018-2026
```
Expected: succeeds without code changes; writes its own output folder.

- [ ] **Step 5: Verify second run is cache-hit (no API calls in log)**

```bash
python -m trader backtest pair_trading \
    --tickers AMD,NVDA \
    --from 2020-01-01 --to 2026-05-01 \
    --out results/pair_amd_nvda_rerun \
    2>&1 | grep -c "Fetching" || echo "0"
```
Expected: prints `0` — second run reads cache, no API calls.

- [ ] **Step 6: Commit results manifest only (not the heavy artifacts)**

`.gitignore` already excludes PNG/CSV outside of `tests/fixtures`. Just commit nothing — Phase 1 is done.

```bash
cd etoro
git status
```
Expected: clean working tree.

---

## Task 11: README update + Phase 1 complete marker

**Files:**
- Modify: `etoro/README.md`

- [ ] **Step 1: Update README status table**

In `etoro/README.md`, change the Phase 1 row to `✅ shipped`, and update the `## Trader (Phase 1)` section: replace `(planned CLI — Phase 1 in progress)` with actual verified examples from Task 10.

- [ ] **Step 2: Commit**

```bash
cd etoro
git add README.md
git commit -m "docs: mark Phase 1 shipped + verified CLI examples"
```

---

## Self-review against spec

- **Strategy roadmap (informational, only #1 in scope):** ✅ pair_trading is the only strategy implemented; base/registry support future strategies (Task 4 + auto-import).
- **Strategy-agnostic framework:** ✅ Task 10 step 4 explicitly proves AMD/NVDA + KO/PEP run identical code.
- **SQLite cache, schema, indices:** ✅ Task 2.
- **Cache-aside loader with gap detection:** ✅ Task 3.
- **BaseStrategy + auto-register:** ✅ Task 4 (metaclass tested).
- **Generic cointegration pair_trading w/ tickers param:** ✅ Task 5.
- **backtrader Cerebro wrapper:** ✅ Task 6.
- **Default analyzers (Sharpe, Sortino, MaxDD, Calmar, WinRate, ProfitFactor, TotalTrades, AvgDuration):** ✅ Task 6 analyzers.py — `extract_metrics` returns every spec key.
- **JSON + CSV + PNG outputs in one folder per run:** ✅ Task 7.
- **CLI: fetch, cache-list, cache-clear, strategies, backtest, sweep:** ✅ Task 8.
- **3-level test pyramid:** unit-cache (Task 2), unit-loader (Task 3), unit-strategy on synthetic data (Task 5), registry (Task 4), smoke end-to-end (Task 9).
- **≥80% coverage on data/ + strategies/:** Task 9 step 4 enforces.
- **Cache persists across runs / separate per ticker:** Task 2 + Task 10 step 5 verifies.
- **No HTTP coupling to back/:** loader imports SDK directly — `back/` is only used for `.env` reuse.
- **Commission + slippage modeled:** Task 6 `run_backtest(commission=0.00005, slippage_perc=0.0001)`.

No placeholders, no TODOs. Plan is complete.
