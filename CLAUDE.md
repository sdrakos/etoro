# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`etoro/` is **one** quantitative-trading project whose components share the same
`back/.env` secrets and data conventions:

- **`back/`** — FastAPI layer. (a) Wrapper over the Massive.com (Polygon.io rebrand) REST API, 104 endpoints across 9 routers; (b) the eToro Public API integration (`back/etoro_api/` typed client + vault, `back/routers/etoro/` proxy/social/portfolio/order routers) for the user's real eToro account. Used directly via HTTP or imported by other tools.
- **`front/`** — **QUANTIQ** web app (React + Vite + TanStack Query/Table + Tailwind). A live eToro **Screener** (category browse + exchange filter + WebSocket live prices) and a **Portfolio** view (open positions + live P&L + close). Talks only to `back/` over the Vite dev proxy. See the QUANTIQ section below.
- **`trader/`** — Phase 1 Python backtesting framework on backtrader. Strategy-agnostic: adding a new strategy is dropping one file under `trader/strategies/`. Default data source is Yahoo (keyless); Massive optional via `--source`.
- **`paper1_RL/`** — Research component: the **Differential Entropic Reward (DER)** paper (`der_paper_full.tex/.pdf`) plus its reproducibility code. Includes the signal-engine + DER-risk-layer alpha experiments (PEAD, sector-neutral momentum, VIX-driven θ) validated on Yahoo 2015–2024 — see `docs/superpowers/specs|plans/2026-06-03-der-alpha-signal-engine*`.
- **`paper2_RL/`** — follow-on research (in progress).
- **`paper3/`** — *"A Disciplined Pipeline for Weak Cross-Sectional Equity Signals"* (PEAD + same-industry lead-lag + utility gate + risk-parity + regime sizing). Built/validated by the `quantiq-pead` skill below.
- **`paper4/`** — *"From Dead Cross-Sectional Momentum to Belief-State Deep Time-Series Momentum"* + a **demo-verified eToro deployment engine**. `paper4/code/`: Kalman LLT + BOCPD belief states feeding a fixed-rule **TSMOM** and an **LSTM Deep Momentum Network** (`dmn.py`, **nested leak-free walk-forward** selection), honest cost-aware eval (Deflated Sharpe, durability). Honest arc (all OOS, net): cross-sectional equity momentum is **dead**, time-series momentum on a **diversified** ETF basket is alive; **diversity > count**; **long-only wins in bulls** (loses crisis protection); **vol-target is the risk/profit dial**; **stop-loss hurts** (whipsaw — tested); BOCPD is the "smart brake". `paper4/engine/`: a CLI (`cli.py`: `signal`/`execute` demo-gated/`retrain`, `--target-vol`, `--vol-method rolling|ewma` — **selectable causal vol-targeting** (trailing-63d rolling or recency-weighted EWMA via `sizing.realized_vol`, front-end-ready), `--strategy rules|ml`) that **opens orders live on the eToro demo** (close by **positionID**; search uses the `items[]` key; **17/18 ETFs on eToro**, DBC missing, BTC available), plus `etoro_backtest.py` on **real eToro candles** (~4y; `--vol-method static|rolling|ewma` + `--compare-vol` overlay — on real prices the causal rolling slightly *beat* static at the same maxDD), `dashboard.html`, and a non-technical **business report** `report_GR.tex/.pdf` (XeLaTeX/Greek, polyglossia, QUANTIQ "Deep Learning Trading" cover, all result tables+figures, cites the paper by title as `(Drakos 2026)`, incl. a measured **diversification section**); plus `engine/correlation_check.py` (**basket-diversification gate**: daily-return correlation heatmap + **effective number of independent bets** ENB=(Σλ)²/Σλ² — on real eToro prices the 5-diversified set scores ENB 4.2/5 vs the 17-ETF set's 3.9/17, the *measured* mechanism behind "diversity > count"), and two Greek beginner **seminars** `lstm_tutorial_GR.tex/.pdf` (neural-net + LSTM theory → our DMN) and `belief_states_tutorial_GR.tex/.pdf` (Kalman LLT + BOCPD belief features), both grounded in the real `dmn.py`/`kalman_llt.py`/`bocpd.py`. Train on Yahoo (deep), serve on eToro. **27 offline tests** (mocked client). Specs/plans: `docs/superpowers/specs|plans/2026-06-06-paper4-changepoint-momentum*` and `*-etoro-engine*`.
- **`paper5/`** — intraday (1h/4h) deep-momentum project (built via the `ai-trading` skill; basis = DMN Lim 2019 + Momentum Transformer Wood 2022; data = Yahoo). **Phase-2 (cost-survivability) done** — findings below. `code/`: `cost_survivability.py` + `_v2.py` (turnover-reduction + crypto + deep daily), `regime_stress.py` (durability-by-year incl. 2022). `engine/etoro_cost_check.py`: live eToro bid/ask via `/api/v1/market-data/instruments/rates`. `tutorial_tests_GR.tex/.pdf`: Greek beginner explainer of the tests (IR, turnover, break-even, with a worked numeric example).
- **`tutorials/`** — Greek beginner explainers (XeLaTeX/DejaVu Serif), e.g. `signals_tutorial_GR.tex` (signals: IC, IR, Newey-West t, gate, √N combination, risk parity).
- **`.Claude/Skills/ai-trading/`** — the reusable **QUANTIQ model-development skill** that encodes the paper4 pipeline: source a bibliography paper → reproduce/critique → evolve on free **Yahoo** data → honest **leak-free, cost-aware** backtest → **eToro engine** (demo first, real gated) → a **novel journal paper** + a non-technical **business report**. `references/`: `methodology-and-evaluation.md` (nested walk-forward, NW-t/DSR/durability, the 10 belief-state features, gotchas), `positioning-strategies.md` (inverse-vol/min-var/Ledoit-Wolf/HRP/fractional-Kelly/vol-target/differential-Sharpe — each mapped to its `Bibliography/position-sizing/` PDF + `paper4/code/sizing.py` impl + results/figures), `etoro-engine.md` (the **exact `/api/v1/…{SEG}` endpoints** + API quirks + gating), `paper-and-report.md` (novelty framing + the XeLaTeX-Greek report recipe). `assets/report_template.tex` (cover+intro, compiles) and `scripts/new_model.py` (scaffold). Use it whenever building/iterating a trading model, an eToro engine/backtest, or the accompanying paper/report.
- **`.Claude/Skills/quantiq-pead/`** — the SEC-EDGAR PEAD/lead-lag engine: point-in-time SUE from EDGAR (no analyst data), Fama-MacBeth own/peer separation, drift/half-life/durability event study, risk-parity combination. `analysis/run_big_universe.py` orchestrates own-PEAD + lead-lag on a wide price panel. `skill/sec-edgar/scripts/fundamentals_api.py` is the consolidated endpoint: `get_fundamentals(ua, tickers)` → all PiT line items in one call, `fundamental_factors(panel)` → value/quality/accruals/investment/buyback factors (the orthogonal signals to combine with PEAD).
- **`Bibliography/`** — curated literature. `intraday-dl-rl-trading/` is an annotated bibliography (`README.md`) of **reputable-only** papers (Oxford-Man/Zohren-Roberts, IEEE TSP/TNNLS, Quant Finance, EJOR, ICML, AAMAS, Math Finance — predatory/paper-mill venues excluded) on LSTM/DMN, RL, and CNN/LOB for intraday (1h/4h) trading, with `download_pdfs.py` (arXiv PDFs are gitignored — re-downloadable). Foundation for the **planned intraday project** below.

Phase status, layout, and end-user CLI examples live in `README.md` — don't duplicate them here.

### Real-data PEAD findings (2026-06, free EDGAR + Yahoo)

Honest, fragile results — **signals are universe/period-dependent** (the paper3 thesis, demonstrated live):
- **own-PEAD**: null on mega-caps (150 names, t=1.2) but **significant when mid-caps included** (401 names 2015-2024, OOS IR 0.74, NW t=2.54, durable) — matches theory (PEAD stronger in smaller names).
- **same-industry lead-lag**: significant only on the narrow 150 mega-cap universe (t=2.61); **null on the broad 401** (t=0.10) → small-universe artifact, fragile.
- **fundamentals** (9 theory-signed value/quality/accruals/investment/buyback factors via `fundamentals_api`): **all fail the gate** at every horizon (monthly→annual). 2015-24 = "value winter" + only ~3 independent annual obs → sample too short for slow factors.
- **net of costs the edge vanishes**: own-PEAD long-short gross +11.2% / IR 0.75, but **net of 5bps spread → +0.1% / IR 0.02** (maxDD −4.2%). A real but economically razor-thin signal; not tradable alone.
- Three real bugs fixed in the skill to get here: EDGAR `sicCode`→`sic`; SUE winsorization (σ→0 gave std 840); event-window filter (events 2011-2026 vs prices → OOS=0/0).
- **Binding constraint is data, not method**: need depth + small-cap breadth + survivorship-free membership (Sharadar/CRSP). None free; see `paper1_RL/DATA_SOURCES.md`.
- Written up in **`paper3/paper_skeleton.tex`** (9 pp, TikZ pipeline + drift/cross-config/fundamentals/PnL figures; honest null). Figures live in `paper3/figures/` (gitignore has a `!paper3/figures/*.png` exception over the global `*.png` ignore — keep it).

### Planned: intraday (1h/4h) deep-momentum project (design basis)

**Chosen architecture basis** (for the new intraday algorithm analogous to paper4):
- **Deep Momentum Networks** (Lim, Zohren, Roberts 2019, arXiv:1904.04912) — an LSTM that outputs the position $X_t\in[-1,1]$ **inside** the volatility-scaling TSMOM framework, trained to **directly maximize Sharpe** (custom loss) with a **turnover-regularization** term; learns trend + sizing jointly. Low-capacity → avoids the overfit the DER paper proved.
- **+ attention via the Momentum Transformer** (Wood, Giegerich, Roberts, Zohren 2022, arXiv:2112.08534) — better regime adaptation than sequential LSTM. PDFs in `Bibliography/intraday-dl-rl-trading/pdfs/`.

**Data source: Yahoo (yfinance).** 1h bars (~730 days of history on Yahoo); **4h is resampled from 1h** (not a native Yahoo interval). Train on Yahoo, serve later on eToro (the paper4 pattern).

**Planned improvements / experiments:** (1) port DMN to 4h; (2) **eToro cost-aware loss** (real spread + overnight financing, not just the paper's 2–3 bps); (3) 1h+4h multi-timeframe fusion; (4) BOCPD changepoint brake (paper4); (5) vol-target as the risk/profit dial; (6) diversified basket incl. crypto (*diversity > count*); (7) quantile/uncertainty sizing (TFT-style).

**First step before building: a cost-survivability probe** — measure the break-even bps of a 4h trend/DMN vs real costs (the whole project arc shows net-of-costs is the killer; paper3 own-PEAD died at 5 bps). If it survives → brainstorm → spec → plan → build.

### paper5 Phase-2 findings (2026-06, free Yahoo + live eToro)

Cost-survivability + regime-stress on a simple vol-targeted TSMOM baseline (no DMN yet — reproduce/critique first):
- **ETF intraday is dead**: 4h gross IR ≈ 0 / negative; break-even ≈ 0.3 bps (1h) — costs annihilate it. **No model fixes turnover.**
- **The no-trade band is the decisive lever**: cuts turnover ~×35 (0.07→0.002) → break-even 5 → **>80 bps**. Mechanism: break-even ≈ gross/turnover, and a direction flip costs **double** (close + open).
- **Crypto banded momentum survives**: 4h break-even >80 bps; **daily** net IR **1.27**, NW-t **2.74**, maxDD **−8%**, and **positive in 2022** (BTC −65%) → not a bull artifact. ETF banded daily also real (net IR 0.57, t=2.30, +in 2022).
- **Live eToro crypto spreads: median ~10 bps** (range 3–32; BTC/ETH ~32) — well under the >80 bps break-even → **survives real costs with margin**.
- **Verdict / direction**: the production-viable core is **crypto (+ETF) banded vol-targeted momentum**; daily is regime-proven, 4h promising but only ~2y of intraday on Yahoo (regime-untestable). The DMN's job is to lift gross edge on this core; deploy daily as the robust base, treat 4h as a live-forward enhancement.

## User preferences (durable)

- **No `Co-Authored-By` footer in commit messages**. Use a clean `git commit -m "..."` with no trailer.
- **Non-technical end users are the audience for the product**. Hide complexity behind small public APIs. Don't bolt on defensive code paths "just in case."
- Conversations are Greek/Greeklish; code is English. Mirror what the user uses.
- **Use Opus 4.8 only** — for this main session *and* every dispatched subagent (pass `model: opus` to the Agent tool). Don't downgrade subagents to Sonnet/Haiku.

## Critical conventions

### Secrets

The single source of truth for `MASSIVE_KEY` is `back/.env`. `trader/config.py` reads it from there — **never duplicate the key** into a second `.env`. The repo's `.gitignore` excludes all `.env` files; `back/.env.example` is the committed template.

The key is **lazy**: `config.py` loads `MASSIVE_KEY` at import without raising, and `config.get_massive_key()` raises `RuntimeError` only when something actually needs it (i.e. `source="massive"`). This lets the whole framework run keyless on the default Yahoo source. Don't reintroduce an import-time raise.

`back/.env` is the single store for **all** project secrets: `MASSIVE_KEY`, the eToro keys (`ETORO_PUBLIC_KEY`, `ETORO_PRIVATE_KEY`), `FINNHUB_API_KEY` (earnings estimates/surprises — free tier = last 4 quarters only), `GIT_HUB_TOKEN` (used for pushes), and the Microsoft Graph email creds (`CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, `USER_EMAIL`) used to send mail via Graph `/sendMail` (e.g. `tutorials/send_graph_email.py` — base64 done in-process, creds never printed). Never duplicate or hard-code these elsewhere; `back/.env.example` is the committed template.

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

### QUANTIQ web app (`front/` + eToro live layer in `back/`)

The QUANTIQ frontend is a multi-view eToro app for **non-technical** users. It runs against `back/` (demo account, app keys from `back/.env`) on **port 8765**; the Vite dev server proxies `/screener`, `/portfolio`, `/charts`, and `/ws` there (`front/vite.config.ts` — **every backend path the UI calls needs a proxy entry**, or you get `Could not load …`). True multitenant per-user keys (X-User-Id → vault) is a future phase; everything below uses `get_server_client()` (shared app keys).

**Backend pieces (all `get_server_client`, demo):**
- `back/data_cache/etoro_catalog.py` — SQLite cache of the eToro instrument catalog (`~/.etoro/etoro_catalog.db`), populated from `/instruments/discover`. `query`/`all_for_category` (text + `exchange` filter), `exchanges(asset_class)`, `get_by_instrument_ids`. **The eToro REST `fields`/docs are aspirational** — real shapes were reverse-engineered (lean discover items; `/rates` returns bid/ask for only a subset; sector is NOT available).
- `back/routers/screener.py` — `GET /screener/category/{cat}` (paginated/sorted/searched + `exchange` param), `GET /screener/exchanges/{cat}`, `/movers`, `/catalog-status`. A FastAPI lifespan loop auto-refreshes the catalog every ~90s so prices don't freeze.
- `back/etoro_api/ws_client.py` + `back/routers/ws_prices.py` — the **price relay**: ONE shared upstream `wss://ws.etoro.com/ws` connection (`EtoroWsClient`, reconnect/backoff) fanned out to browsers over `GET(ws) /ws/prices`. `PriceRelay` ref-counts instrument subscriptions, computes live change% from prevClose, drops dead clients without breaking fan-out. **The real WS tick frame has NO `type` field and string-typed `Bid/Ask/LastExecution`** — `parse_messages` handles that.
- `back/routers/portfolio.py` — `GET /portfolio/positions` (normalizes `clientPortfolio.positions[]` + enriches symbol/name/seed-rate from the catalog), `POST /portfolio/close/{id}` (demo market-close; `guard_real()` for real, gated by `QUANTIQ_ALLOW_REAL_EXECUTION`).
- `back/routers/chart.py` — `GET /charts/{instrument_id}?interval&count` → normalized OHLCV for the chart. eToro candles are **double-nested** (`data["candles"][0]["candles"]`, newest-first) — flattened to ascending **epoch-ms** candles, incomplete rows dropped, symbol/name enriched from the catalog.

**Frontend (`front/src/`):** `views/ScreenerView.tsx` + `views/PortfolioView.tsx` behind `components/AppNav.tsx`; `App.tsx` is a thin shell. `hooks/usePriceStream.ts` is the browser WS client (reconnect, `Map<id,LiveTick>`); the screener/portfolio overlay live ticks on REST "seed" rows. **Live P&L is computed frontend-side** (`lib/pnl.ts`: `units*(price-open_rate)*(is_buy?1:-1)`) — the same `/ws/prices` relay drives both screener prices and portfolio P&L. The app uses `react-router-dom`: clicking a ticker → `openChart(id)` (`window.open`) opens a new tab at `/chart/:instrumentId` → `views/ChartView.tsx` renders a **KLineCharts** candlestick (`components/Chart.tsx`, canvas; **mocked in tests** since jsdom has no canvas) with timeframe + TA-indicator toolbar and a live last-candle from `/ws/prices`. Each active indicator has a ⚙️ → `components/IndicatorSettingsModal.tsx` (Inputs = `calcParams`, Style = a **swatch palette**, NOT a native `<input type=color>` which pops over the modal); indicators are config objects (`lib/indicators.ts`). **KLineCharts gotcha (cost a debugging session):** the `styles.lines` you pass to `createIndicator`/`overrideIndicator` MUST be **complete** line objects (`{show,size,style,smooth,color,dashedValue}`) — a partial `{color}` silently breaks figure-generation so `indicator.result` stays `undefined` and `drawImp` crashes on **every** redraw (dead mouse/zoom + invisible indicators). Unit tests mock KLineCharts so they can't catch this — verify chart changes live (Playwright/devtools MCP against `npm run dev`). **Naming:** backend API is `/charts` (plural), frontend route is `/chart` (singular) — keep them distinct so the proxy doesn't swallow the route. Tests are fully offline (Vitest + MSW; async backend tests use `asyncio.run`, no `pytest-asyncio`).

**Specs/plans** for all of the above live in `docs/superpowers/specs|plans/2026-06-04-screener-*`, `2026-06-04-portfolio-*`, , `2026-06-05-instrument-chart*`, and `2026-06-05-indicator-settings-modal*`. **Deferred:** sector/industry filter (no cheap data source); WebSocket-true multitenant; chart drawing-tools UI / save layouts; per-indicator persistence (each chart tab starts from defaults).

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

### front/ (QUANTIQ web app)

```bash
cd back && python -m uvicorn main:app --reload --port 8765   # backend MUST run first (proxy target)
cd front && npm run dev          # Vite dev server :5173 (proxies /screener,/portfolio,/ws → 8765)
cd front && npm run test:run     # Vitest (offline, MSW)
cd front && npm run build        # tsc -b && vite build
```

`back/` tests for the eToro/QUANTIQ layer: `cd back && python -m pytest tests/ -q` (offline; `test_etoro_*`, `test_screener_*`, `test_price_relay`, `test_ws_prices_endpoint`, `test_portfolio`). If the UI shows `Could not load …` while the screener works, a backend path is missing from the Vite proxy — add it to `front/vite.config.ts` and restart `npm run dev`.

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

### Future (second phase, to design — not built yet): broker-agnostic `quantiq-trading` library + API

The `paper4/engine/` is **already ~90% broker-agnostic** — only `etoro_adapter.py` knows about eToro
(`signal_engine`/`rebalancer`/`sizing`/`features`/`metrics` are pure). The plan for "run on any
platform, not just eToro" is a **refactor, not a rewrite**: extract the engine core into an
installable **`quantiq-trading` package** and make eToro one plugin behind a `BrokerAdapter`
protocol (`search` / `candles` / `positions` / `submit`), registered in a `_BROKERS` dict — exactly
the proven plugin pattern of `trader/data/sources/` (`_SOURCES = {"yahoo","massive"}`, one file per
source). Layering: **library first** (the logic + broker plugins, `pip install quantiq-trading[etoro|all]`,
extras per broker like `agelclaw`), then a thin **FastAPI service** on top (`/signal` `/execute`
`/backtest`, with `broker` as a param), then UI/n8n/3rd-party as consumers. The `ai-trading` skill is
the *methodology*; this library would be the *tool*. **Honest hard 10%:** per-broker symbology,
order model (netting vs hedging, by-amount vs by-units, close-by-positionID vs by-symbol), asset
coverage, fees/financing/market-hours, auth/segments — each new broker needs its own mapping +
offline (mocked) tests. When we pick this up: go brainstorming → spec → plan; decide library/research
boundary (what leaves `paperN/`), the second target broker (Alpaca/IBKR/Binance?), and coexistence
with the existing `trader/` package.

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
