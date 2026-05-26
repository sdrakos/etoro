# Trader Platform — Phase 1: Strategy + Backtest Core

**Status:** Design approved 2026-05-27
**Owner:** sdrakos
**Scope:** Generic strategy + backtest framework. AMD/NVDA pair trading is the **first** strategy shipped — not the only one. New strategies will be added by dropping a file under `strategies/`.

## Context

The user is building an end-state TradingView-style platform for running and backtesting strategies on US equities (TSLA/NVDA/AMD focus per the Notion plan). The full vision (screener, charts, options chain, portfolio, paper trading) is decomposed into 6 phases. This spec covers **Phase 1**: the Python core that defines strategies, loads historical data, runs backtests, and emits performance metrics. Subsequent phases (screener UI, charts, strategy UI, options chain, portfolio) are out of scope and will have their own specs.

The Massive.com (Polygon.io rebrand) REST API is already wrapped in a FastAPI service at `back/` with 104 endpoints. Phase 1 reuses the same `polygon-api-client` SDK directly for data fetching — it does not call the FastAPI service over HTTP (no need to run a server for a backtest).

## Goals

1. Define a **strategy-agnostic** `BaseStrategy` interface. Adding a new strategy is dropping one file under `strategies/` — no changes to engine, data layer, or CLI required.
2. The CLI auto-discovers strategies from `strategies/` and exposes their parameters as flags via dataclass introspection.
3. Ship one concrete strategy first: generic **cointegration pair trading** (parameterized by ticker pair). First run: AMD/NVDA. Same code runs KO/PEP, GOOGL/META, etc., by changing flags.
4. Build a local SQLite cache so historical bars persist across runs; pulling new tickers extends the cache without touching existing data.
5. Run event-driven backtests with backtrader, including realistic commission/slippage.
6. Emit machine-readable metrics (JSON), human-readable artifacts (CSV, PNG), and bar-by-bar debug logs.
7. Provide a CLI for data preload, single backtests, parameter sweeps, and cache inspection.

### Strategy roadmap (informational — only #1 in Phase 1 scope)

| # | Strategy | Asset class | Phase |
|---|---|---|---|
| 1 | Cointegration pair trading (generic) | Equities | **1 (this spec)** |
| 2 | Macro-overlay momentum (VIX/yield-curve regime) | ETFs + macro | 1.5 |
| 3 | Single-name mean reversion (RSI + Bollinger) | Equities | 1.5 |
| 4 | News-driven event momentum | Equities + news | 1.5 |
| 5 | Earnings IV crush | Options | 5 (needs paid IV history) |
| 6 | PEAD (post-earnings drift) | Equities | later |

Strategies 2-4 reuse Phase 1 infrastructure with no framework changes — only new files under `strategies/`.

## Non-goals

- Live or paper trading execution (Phase 6).
- Web UI (Phase 4).
- Options strategies (Phase 5 — IV crush needs historical IV data which requires a paid Massive plan).
- Multi-strategy portfolio allocation / risk parity (later phase).
- Cloud-hosted database (SQLite local is sufficient for solo dev).

## Architecture

### Directory layout

```
etoro/
├── back/                       (existing — FastAPI wrapper, untouched)
└── trader/                     (new — Phase 1)
    ├── data/
    │   ├── cache.py            # SQLite store
    │   └── loader.py           # cache-aside fetcher
    ├── strategies/
    │   ├── __init__.py         # auto-registers any strategy that subclasses BaseStrategy
    │   ├── base.py             # BaseStrategy ABC + StrategyRegistry
    │   └── pair_trading.py     # generic cointegration pair (any 2 tickers)
    │   # future: momentum.py, mean_reversion.py, news_event.py, ...
    ├── engine/
    │   ├── runner.py           # backtrader Cerebro wrapper
    │   ├── analyzers.py        # Sharpe, Sortino, Max DD, win-rate, profit-factor
    │   └── report.py           # JSON + PNG + CSV output
    ├── cli.py                  # python -m trader ...
    ├── tests/
    │   ├── fixtures/           # ~50 days of AMD/NVDA for offline tests
    │   ├── test_cache.py
    │   ├── test_pair_strategy.py
    │   └── test_smoke.py
    └── requirements.txt
```

Module boundaries: `data/` knows about timeseries, not strategies. `strategies/` receives ready DataFrames, doesn't fetch. `engine/` orchestrates. Each layer testable independently.

### Data layer

**Storage:** SQLite at `~/.etoro/cache.db` (single-file, zero-ops).

**Schema:**

```sql
CREATE TABLE bars (
    ticker     TEXT NOT NULL,
    timestamp  INTEGER NOT NULL,       -- Unix milliseconds (Massive convention)
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    vwap       REAL,
    adjusted   INTEGER DEFAULT 1,       -- 1 = adjusted for splits/dividends
    timespan   TEXT DEFAULT 'day',      -- day | hour | minute
    PRIMARY KEY (ticker, timestamp, timespan)
);
CREATE INDEX idx_bars_ticker_range ON bars(ticker, timespan, timestamp);
```

Each ticker is stored independently. Studying AMD/NVDA writes those two; later studying TSLA adds TSLA without touching AMD/NVDA. This is the local "data warehouse" — it grows monotonically with the universe the user explores.

**Public API:**

```python
def load_bars(ticker: str, start: date, end: date,
              timespan: str = "day") -> pd.DataFrame:
    """
    Cache-aside pattern:
    1. Query cache for [start, end] coverage gaps.
    2. Fetch only missing ranges from Massive API.
    3. UPSERT into cache.
    4. Return full requested slice, DatetimeIndex (UTC).
    """
```

**Why cache-aside vs pre-download everything:** A first fetch for AMD/NVDA daily 2015-today is one API call per ticker (2 total). Subsequent runs read from SQLite in milliseconds. Extending the range pulls only the delta. No wasted bandwidth, no stale data problem within a session.

**No HTTP coupling to back/:** The loader imports `polygon-api-client` directly. The FastAPI service in `back/` is for external consumers (future web UI, n8n, etc.) — a backtest does not need a server.

### Strategy interface

**`strategies/base.py`** — strategy-agnostic base class + registry:

```python
class BaseStrategy(bt.Strategy):
    """
    Adds standard hooks to backtrader's Strategy:
    - name: short identifier used by CLI (e.g. "pair_trading", "momentum")
    - description: one-line summary shown by `python -m trader strategies`
    - params_dataclass: dataclass that defines strategy parameters
    - required_tickers(params) -> list[str] | None: tickers the strategy needs.
        Return None if user supplies via --tickers; return a fixed list if hardcoded.
    - log_trade(side, ticker, size, price, reason): writes to self._trade_log
    - cleanup(): closes outstanding positions at end of run
    """
    name: str
    description: str
    params_dataclass: type

# Auto-registration on subclass creation (no manual list to update):
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {}

class _AutoRegister(type(bt.Strategy)):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(cls, "name", None) and cls.__name__ != "BaseStrategy":
            STRATEGY_REGISTRY[cls.name] = cls
```

Each strategy declares its parameters as a dataclass so the CLI derives flags (`--lookback`, `--entry-z`, ...) automatically via `argparse` introspection. **Adding a new strategy = one new file under `strategies/`.** No edits to engine, data, CLI, or this base class.

**`strategies/pair_trading.py`** — generic cointegration pair trading (any 2 tickers).

Parameters:

```python
@dataclass
class PairParams:
    tickers: tuple[str, str]         # (e.g.) ("AMD", "NVDA") — passed via --tickers
    lookback: int = 60               # rolling window for OLS hedge ratio
    entry_z: float = 2.0             # |z| > entry_z opens position
    exit_z: float = 0.5              # |z| < exit_z closes position
    stop_loss_z: float = 3.5         # |z| > stop_loss_z emergency exit
    capital_per_leg: float = 50_000  # equal dollar long-short sizing
    min_p_value: float = 0.05        # cointegration ADF p-value threshold
```

The same strategy runs on any pair: AMD/NVDA, KO/PEP, GOOGL/META, XOM/CVX, etc.

Per-bar logic (event-driven):

```
1. Compute hedge ratio β via OLS on last `lookback` days:
       NVDA_t = α + β · AMD_t + ε_t
2. Spread_t = NVDA_t − β · AMD_t
3. z_t     = (Spread_t − μ_lookback) / σ_lookback
4. Run ADF test on spread; skip trading this bar if p > min_p_value.
5. Signals:
   - flat & z > +entry_z      → SHORT NVDA / LONG AMD   (spread overextended high)
   - flat & z < −entry_z      → LONG NVDA / SHORT AMD   (spread overextended low)
   - in pos & |z| < exit_z    → close both legs (mean reverted)
   - in pos & |z| > stop_loss_z → emergency close (divergence widening)
```

**Sizing rule:** equal dollar across legs (not equal shares). This keeps the dollar spread stable as prices move.

**Costs modeled:** 0.5 bps commission + 1 bp slippage per leg per fill (realistic for retail at IBKR / Alpaca).

### Engine

**`engine/runner.py`** orchestrates backtrader:

```python
def run_backtest(
    strategy_cls: type[BaseStrategy],
    params: dict,
    tickers: list[str],
    start: date,
    end: date,
    capital: float = 100_000,
    timespan: str = "day",
) -> BacktestResult:
    """
    1. load_bars() per ticker → bt.feeds.PandasData feeds.
    2. cerebro.adddata + addstrategy(params) + addanalyzer(*analyzers).
    3. cerebro.broker.setcash(capital), setcommission, set_slippage_perc.
    4. cerebro.run().
    5. Pull analyzer results + strategy._trade_log → BacktestResult.
    """
```

**Analyzers (`engine/analyzers.py`):**

| Metric | Definition |
|---|---|
| Total Return | (final − initial) / initial |
| CAGR | Annualized compound return |
| Sharpe | mean(daily_return) / std(daily_return) × √252 |
| Sortino | mean(daily_return) / std(downside_return) × √252 |
| Max Drawdown | min peak-to-trough equity decline |
| Calmar | CAGR / |Max DD| |
| Win Rate | wins / total_trades |
| Profit Factor | sum(winning P&L) / |sum(losing P&L)| |
| Total Trades | round-trip count |
| Avg Trade Duration | mean days held per round-trip |

**Result shape:**

```python
@dataclass
class BacktestResult:
    strategy: str
    params: dict
    tickers: list[str]
    period: tuple[date, date]
    metrics: dict[str, float]
    equity_curve: pd.Series        # daily portfolio value
    trades: pd.DataFrame           # one row per round-trip
    drawdown_series: pd.Series
```

### CLI

```bash
# Data ops
python -m trader fetch AMD,NVDA,TSLA --from 2015-01-01 --to today
python -m trader cache-list
python -m trader cache-clear TSLA

# Backtest a single config — any pair, same code
python -m trader backtest pair_trading \
    --tickers AMD,NVDA \
    --from 2020-01-01 --to 2026-05-01 \
    --capital 100000 \
    --lookback 60 --entry-z 2.0 --exit-z 0.5 \
    --out results/pair_amd_nvda_2020-2026

python -m trader backtest pair_trading \
    --tickers KO,PEP \
    --from 2018-01-01 --to 2026-05-01 \
    --out results/pair_ko_pep_2018-2026

# Parameter sweep (grid search) — same pattern any strategy
python -m trader sweep pair_trading \
    --tickers AMD,NVDA \
    --from 2020-01-01 --to 2026-05-01 \
    --lookback 30,45,60,90 --entry-z 1.5,2.0,2.5 \
    --out results/sweep_001/

# Discovery — lists every strategy auto-registered from strategies/
python -m trader strategies
# → pair_trading      Generic cointegration pair trading (2 tickers)
#   momentum          (when added in Phase 1.5)
#   mean_reversion    (when added in Phase 1.5)
```

**Output per run** (one folder per backtest):

```
results/pair_2020-2026/
├── result.json           # metrics + params + period + run timestamp
├── equity_curve.png      # portfolio value + SPY benchmark
├── drawdown.png          # underwater chart
├── trades.csv            # round-trip-level detail
├── z_score.png           # z-score timeseries + entry/exit markers
└── run.log               # bar-by-bar decisions for debugging
```

Example `result.json`:

```json
{
  "strategy": "amd_nvda_pair",
  "period": ["2020-01-01", "2026-05-01"],
  "params": {"lookback": 60, "entry_z": 2.0, "exit_z": 0.5},
  "metrics": {
    "total_return": 0.412,
    "cagr": 0.058,
    "sharpe": 1.34,
    "sortino": 1.82,
    "max_drawdown": -0.092,
    "calmar": 0.63,
    "win_rate": 0.62,
    "profit_factor": 1.78,
    "total_trades": 47,
    "avg_trade_days": 18.2
  },
  "run_at": "2026-05-27T12:00:00Z"
}
```

## Testing

Three levels, each verifying a different concern.

**Unit — cache (`tests/test_cache.py`):**
- `test_upsert_idempotent`: inserting the same bar twice doesn't create duplicates.
- `test_partial_range_fetch`: with cache holding 2020-01-01..2024-12-31, requesting 2020-06-01..2025-06-30 calls the API only for 2025-01-01..2025-06-30.
- `test_missing_data_returns_empty`: unknown ticker returns an empty DataFrame, not an exception.

**Unit — strategy (`tests/test_pair_strategy.py`):**
- `test_known_cointegrated_series`: synthetic NVDA_t = 2·AMD_t + N(0,1). ADF p-value < 0.01. At z = +2.5 the strategy must open short-NVDA / long-AMD; at z near 0 it must close.
- `test_p_value_filter`: two independent random walks (not cointegrated) — strategy must not open any trade.
- `test_stop_loss_triggers`: z spike to 4.0 → emergency exit regardless of exit_z.

**Smoke — end-to-end (`tests/test_smoke.py`):**
- Pre-load cache with fixture bars (~50 days AMD/NVDA, 2023). Run `run_backtest` for the period.
- Assert `result.json` exists, metrics dict has all expected keys, equity curve length equals trading days, total trades in a sane range (0 < n < 50).

**Tooling:** `pytest` + `pytest-cov`. Target ≥ 80% coverage on `data/` and `strategies/`. Fixtures live under `tests/fixtures/` so the suite runs fully offline (no API calls).

## Open questions / future work

- **Walk-forward validation:** out-of-sample testing with rolling windows is needed before trusting any result. Considered "best practice" follow-up after Phase 1 ships.
- **Persistence of results:** currently filesystem only. If Phase 4 (Strategy UI) needs querying, a `results` table in SQLite or Supabase will be added then.
- **Live trading bridge:** intentionally not designed here. backtrader supports broker integrations (IBKR, Alpaca) — adding them is a Phase 6 task.
- **Strategy combination / portfolio overlay:** running multiple strategies in parallel with capital allocation is later. Phase 1 is one strategy per backtest run.

## Dependencies

```
backtrader>=1.9.78
pandas>=2.0
numpy>=1.24
statsmodels>=0.14         # cointegration / ADF tests
polygon-api-client>=1.14  # reuse from back/
python-dotenv>=1.0
matplotlib>=3.7           # plots
pytest>=8.0
pytest-cov>=5.0
```

`requirements.txt` lives under `trader/`. Install with `pip install -r trader/requirements.txt`.

## Success criteria

Phase 1 is done when:

1. `python -m trader fetch AMD,NVDA --from 2015-01-01` populates the SQLite cache.
2. `python -m trader backtest pair_trading --tickers AMD,NVDA --from 2020-01-01 --to 2026-05-01 --out results/r1` produces the full output folder.
3. The same command with `--tickers KO,PEP` works without code changes — proving strategy is ticker-agnostic.
4. `python -m trader strategies` lists `pair_trading` (and any new strategy dropped into `strategies/` later — verified by adding a stub).
5. All tests pass with ≥ 80% coverage on `data/` and `strategies/`.
6. A second run on the same period skips the API call (cache hit verified in logs).
