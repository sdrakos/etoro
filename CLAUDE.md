# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`etoro/` is **one** quantitative-trading project with four components that share the same
`back/.env` secrets and data conventions:

- **`back/`** — FastAPI layer. (a) Wrapper over the Massive.com (Polygon.io rebrand) REST API, 104 endpoints across 9 routers; (b) the eToro Public API integration (`back/etoro_api/` typed client + vault, `back/routers/etoro/` proxy/social/portfolio/order routers) for the user's real eToro account. Used directly via HTTP or imported by other tools.
- **`trader/`** — Phase 1 Python backtesting framework on backtrader. Strategy-agnostic: adding a new strategy is dropping one file under `trader/strategies/`. Default data source is Yahoo (keyless); Massive optional via `--source`.
- **`paper1_RL/`** — Research component: the **Differential Entropic Reward (DER)** paper (`der_paper_full.tex/.pdf`) plus its reproducibility code. Includes the signal-engine + DER-risk-layer alpha experiments (PEAD, sector-neutral momentum, VIX-driven θ) validated on Yahoo 2015–2024 — see `docs/superpowers/specs|plans/2026-06-03-der-alpha-signal-engine*`.
- **`paper2_RL/`** — follow-on research (in progress).

Phase status, layout, and end-user CLI examples live in `README.md` — don't duplicate them here.

## User preferences (durable)

- **No `Co-Authored-By` footer in commit messages**. Use a clean `git commit -m "..."` with no trailer.
- **Non-technical end users are the audience for the product**. Hide complexity behind small public APIs. Don't bolt on defensive code paths "just in case."
- Conversations are Greek/Greeklish; code is English. Mirror what the user uses.

## Critical conventions

### Secrets

The single source of truth for `MASSIVE_KEY` is `back/.env`. `trader/config.py` reads it from there — **never duplicate the key** into a second `.env`. The repo's `.gitignore` excludes all `.env` files; `back/.env.example` is the committed template.

The key is **lazy**: `config.py` loads `MASSIVE_KEY` at import without raising, and `config.get_massive_key()` raises `RuntimeError` only when something actually needs it (i.e. `source="massive"`). This lets the whole framework run keyless on the default Yahoo source. Don't reintroduce an import-time raise.

`back/.env` is the single store for **all** project secrets: `MASSIVE_KEY`, the eToro keys (`ETORO_PUBLIC_KEY`, `ETORO_PRIVATE_KEY`), and `GIT_HUB_TOKEN` (used for pushes). Never duplicate or hard-code these elsewhere; `back/.env.example` is the committed template.

### Adding a new strategy

1. Create `trader/strategies/<name>.py`
2. Define a `@dataclass` with the strategy's params (first field can be `tickers: tuple[str, str]` if it's a pair strategy)
3. Subclass `BaseStrategy` and set `name`, `description`, `params_dataclass`, and the backtrader `params` tuple
4. Implement `next()` using `self.datas[i]` and `self.log_trade(...)`
5. That's it — `STRATEGY_REGISTRY` auto-populates on import (metaclass in `trader/strategies/base.py`)

The CLI (`python -m trader strategies`, `backtest`, `sweep`) discovers it automatically; flags are derived from the dataclass via `argparse` introspection in `trader/cli.py::_attach_strategy_flags`.

Don't manually register strategies anywhere. Don't import strategies in `__init__.py` — `pkgutil.iter_modules` does the walk.

### Data layer

`trader/data/loader.py::load_bars` is **cache-aside**: it queries SQLite first (`~/.etoro/cache.db`), fetches only the missing range from the chosen source, upserts, and returns a DataFrame. The cache is keyed `(ticker, timestamp, timespan, source)` — each ticker **and source** stored independently; new tickers/sources extend without disturbing existing ones.

**Two sources, Yahoo is the default.** `load_bars(ticker, start, end, timespan="day", source="yahoo")`. Each provider lives in `trader/data/sources/` and exposes the same `fetch_bars(ticker, start, end, timespan) -> list[dict]`:

- **`yahoo.py`** — free, keyless, adjusted daily bars via `yfinance` (`auto_adjust=True`). `vwap` is always `None`; yfinance's `end` is exclusive so it fetches `end + 1 day`.
- **`massive.py`** — Massive/Polygon REST SDK (`list_aggs`), needs `get_massive_key()`. This is the old `loader.py` fetch logic, extracted.

`loader.py` is **source-agnostic** — it dispatches via `_SOURCES = {"yahoo": yahoo, "massive": massive}` and computes cache gaps **per source**. Adding a third source = drop one `sources/<name>.py` with a `fetch_bars` + register it in `_SOURCES`. An unknown `source` raises `ValueError`.

**Source isolation matters.** Because `source` is in the cache PK, Yahoo and Massive bars for the same ticker never collide (adjusted prices differ slightly between providers). A backtest with no `--source` hits the Yahoo partition; it won't read previously-cached Massive data and will fresh-fetch from Yahoo. That's intentional — pass `--source massive` to reuse Massive data.

**Cache migration is automatic.** `Cache.__init__` detects a pre-multi-source DB (no `source` column) and rebuilds the table once, tagging all existing rows `source='massive'` (everything cached before this feature came from Massive). The `SCHEMA` and `_MIGRATE_ADD_SOURCE` table definitions in `cache.py` must be kept in sync.

**`load_bars` only supports `timespan="day"`**. Intraday raises `NotImplementedError` because gap math currently truncates to dates. Don't lift the guard without redoing the gap calculation in datetime precision.

### `back/` ↔ `trader/` boundary

`trader/` does **not** HTTP-call `back/`. For the Massive source, both import the same `polygon` / `massive` Python SDK directly; for the Yahoo source `trader/` uses `yfinance`. `back/` is Massive-only and for external consumers (future web UI, n8n, etc.) — backtests don't need a server running.

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
python -m trader cache-list          # what's in ~/.etoro/cache.db (shows source per row)
python -m trader fetch AMD --from 2024-01-01 --to today              # Yahoo (default, keyless)
python -m trader fetch AMD --from 2024-01-01 --to today --source massive   # Massive (needs key, ≤2y Basic tier)
```

`--source {yahoo,massive}` (default `yahoo`) is also accepted by `backtest` and `sweep`. `cache-clear` takes an optional `--source` (omit to clear all sources for the ticker).

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
