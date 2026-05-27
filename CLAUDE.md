# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`etoro/` is a quantitative trading platform with two shipped components:

- **`back/`** — FastAPI wrapper over the Massive.com (Polygon.io rebrand) REST API. 104 endpoints across 9 routers. Used directly via HTTP or imported by other tools.
- **`trader/`** — Phase 1 Python backtesting framework on backtrader. Strategy-agnostic: adding a new strategy is dropping one file under `trader/strategies/`.

Phase status, layout, and end-user CLI examples live in `README.md` — don't duplicate them here.

## User preferences (durable)

- **No `Co-Authored-By` footer in commit messages**. Use a clean `git commit -m "..."` with no trailer.
- **Non-technical end users are the audience for the product**. Hide complexity behind small public APIs. Don't bolt on defensive code paths "just in case."
- Conversations are Greek/Greeklish; code is English. Mirror what the user uses.

## Critical conventions

### Secrets

The single source of truth for `MASSIVE_KEY` is `back/.env`. `trader/config.py` reads it from there — **never duplicate the key** into a second `.env`. The repo's `.gitignore` excludes all `.env` files; `back/.env.example` is the committed template.

### Adding a new strategy

1. Create `trader/strategies/<name>.py`
2. Define a `@dataclass` with the strategy's params (first field can be `tickers: tuple[str, str]` if it's a pair strategy)
3. Subclass `BaseStrategy` and set `name`, `description`, `params_dataclass`, and the backtrader `params` tuple
4. Implement `next()` using `self.datas[i]` and `self.log_trade(...)`
5. That's it — `STRATEGY_REGISTRY` auto-populates on import (metaclass in `trader/strategies/base.py`)

The CLI (`python -m trader strategies`, `backtest`, `sweep`) discovers it automatically; flags are derived from the dataclass via `argparse` introspection in `trader/cli.py::_attach_strategy_flags`.

Don't manually register strategies anywhere. Don't import strategies in `__init__.py` — `pkgutil.iter_modules` does the walk.

### Data layer

`trader/data/loader.py::load_bars` is **cache-aside**: it queries SQLite first (`~/.etoro/cache.db`), fetches only the missing range from the Massive SDK, upserts, and returns a DataFrame. The cache is keyed `(ticker, timestamp, timespan)` — each ticker stored independently; new tickers extend without disturbing existing ones.

**`load_bars` only supports `timespan="day"`**. Intraday raises `NotImplementedError` because gap math currently truncates to dates. Don't lift the guard without redoing the gap calculation in datetime precision.

### `back/` ↔ `trader/` boundary

`trader/` does **not** HTTP-call `back/`. Both import the same `polygon` / `massive` Python SDK directly. `back/` is for external consumers (future web UI, n8n, etc.) — backtests don't need a server running.

### Sharpe/Sortino on zero-trade backtests

`extract_metrics` in `trader/engine/analyzers.py` returns `None` for `sharpe`/`sortino` when `total_trades == 0`. Otherwise a flat strategy looks catastrophic. Don't revert this guard.

### `argparse` `from_` workaround

`from` is a Python keyword, so CLI subparsers use `dest="from_"` for the `--from` flag. When extending the CLI, follow the same pattern.

### Windows console

`trader/__main__.py` reconfigures stdout/stderr to UTF-8 on Windows so unicode characters in CLI output don't crash on cp1253 locales. Keep this — it's not redundant.

## Commands

All commands assume cwd is `etoro/`.

### back/ (FastAPI dev server)

```bash
cd back && python -m uvicorn main:app --reload --port 8765
# → http://127.0.0.1:8765/docs
```

### trader/ tests

```bash
# Full suite with coverage
python -m pytest trader/tests/ -v --cov=trader --cov-report=term-missing

# Single test file
python -m pytest trader/tests/test_cache.py -v

# Single test
python -m pytest trader/tests/test_pair_trading.py::test_hedge_ratio_recovers_known_beta -v

# Skip the smoke test (requires fixtures already present)
python -m pytest trader/tests/ -v --ignore=trader/tests/test_smoke.py
```

Tests are fully offline. Fixtures in `trader/tests/fixtures/*.csv` are UTC-anchored and gitignored by the global rule but committed with `git add -f`.

### trader/ CLI smoke

```bash
python -m trader strategies          # lists auto-registered strategies
python -m trader cache-list          # what's in ~/.etoro/cache.db
python -m trader fetch AMD --from 2024-01-01 --to today   # ≤2y of data on Basic tier
```

### Linting / formatting

No linter or formatter is configured. The codebase is plain Python 3.11+ with type hints and `from __future__ import annotations` throughout. Follow existing patterns.

## Architecture notes

### Layer rule: data → strategies → engine → CLI

`trader/data/` knows about timeseries and SQLite, nothing about strategies. `trader/strategies/` consumes DataFrames and emits backtrader signals — it doesn't fetch. `trader/engine/` orchestrates Cerebro + analyzers. `trader/cli.py` is the entry point. Each layer is independently testable; circular imports are forbidden.

### Sortino is computed manually

`bt.analyzers.SortinoRatio` does **not exist** in backtrader despite the documentation suggesting it does. `trader/engine/analyzers.py::_compute_sortino` computes it from the `TimeReturn` analyzer's daily returns. If you're adding more risk metrics, follow the same pattern (extract from `TimeReturn` rather than trying to use a non-existent built-in).

### Metaclass composition with backtrader

`trader/strategies/base.py::_AutoRegisterMeta` extends `type(bt.Strategy)` — not just `type`. backtrader's `MetaStrategy` does its own subclass machinery; your metaclass MUST inherit from it or `class BaseStrategy(bt.Strategy, metaclass=...)` blows up at class-creation time. The metaclass `__init__` accepts `*args, **kwargs` for forward-compat.

### Strategy auto-discovery is fault-tolerant

`trader/strategies/__init__.py` walks the package with `pkgutil.iter_modules` and wraps each `importlib.import_module` in `try/except` + `warnings.warn`. A broken strategy module doesn't kill the CLI; it just won't appear in the registry. Skip `_`-prefixed modules (helpers).

### Free-tier Massive limits

5 calls/min, ~2 years of history. The cache absorbs both: subsequent backtests on the same range hit zero API calls. When live-testing, prefer date ranges starting within the last 2 years to avoid `NOT_AUTHORIZED` errors.

## Where things live

- Design specs: `docs/superpowers/specs/`
- Implementation plans: `docs/superpowers/plans/`
- Skills used during development: `.Claude/Skills/` (massive-api-skill, etc.)
- Local SQLite cache: `~/.etoro/cache.db` (gitignored)
- Backtest output folders: `results/` (gitignored)
