# etoro — Trading Strategy & Backtest Platform

Quantitative trading platform that integrates with the Massive.com (Polygon.io rebrand) market data API. Designed for solo development with a path to a TradingView-style UI.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Massive REST API wrapper (FastAPI, 104 endpoints) | ✅ shipped |
| **1** | **Strategy + backtest core (Python, backtrader)** | **✅ shipped** |
| 1.5 | Additional strategies (momentum, mean reversion, news event) | planned |
| 2 | Screener UI (filterable table) | planned |
| 3 | Charts (candlestick + indicators) | planned |
| 4 | Strategy UI (web form to run backtests) | planned |
| 5 | Options chain + Greeks (Earnings IV crush strategy) | planned |
| 6 | Portfolio + paper trading | planned |

## Layout

```
etoro/
├── back/            FastAPI wrapper over Massive.com API (104 endpoints)
├── trader/          (Phase 1) Python strategy + backtest framework
├── front/           (Phase 2+) web UI
├── docs/            specs, plans, design notes
└── .Claude/         Claude Code skills used during development
```

## Backend API (back/)

The FastAPI service wraps the Massive.com SDK and exposes endpoints across 9 categories: stocks, options, indices, crypto, forex, economy, news, filings, market reference.

### Setup

```bash
cd back
pip install -r requirements.txt
cp .env.example .env       # paste your MASSIVE_KEY
python -m uvicorn main:app --reload --port 8765
```

- Interactive docs: `http://127.0.0.1:8765/docs`
- OpenAPI JSON: `http://127.0.0.1:8765/openapi.json`

### Example calls

```bash
GET /stocks/aggs/NVDA?from=2026-01-01&to=2026-05-26&timespan=day
GET /options/chain/AAPL?expiration_date_gte=2026-06-01&contract_type=call
GET /filings/form-4?ticker=TSLA
GET /stocks/indicators/rsi/NVDA?window=14
GET /economy/treasury-yields?date_gte=2025-01-01
```

## Trader (Phase 1)

Strategy-agnostic backtesting framework on backtrader. Drop a `.py` under `trader/strategies/` and it auto-registers — the CLI discovers it automatically. First strategy: generic cointegration pair trading (any 2 tickers).

- Design spec: `docs/superpowers/specs/2026-05-27-trader-phase1-backtest-core-design.md`
- Implementation plan: `docs/superpowers/plans/2026-05-27-trader-phase1.md`
- 27 tests, 88% coverage on `data/` + `strategies/`

### Setup

```bash
cd etoro
pip install -r trader/requirements.txt
# Uses MASSIVE_KEY from etoro/back/.env — no duplicate config
```

### Verified CLI commands

```bash
# Preload cache (one API call per ticker, persistent SQLite at ~/.etoro/cache.db)
python -m trader fetch AMD,NVDA --from 2023-01-01 --to today

# List what's cached
python -m trader cache-list

# List registered strategies (auto-discovered from strategies/)
python -m trader strategies
# → pair_trading   Generic cointegration pair trading (any 2 tickers)

# Run one backtest config
python -m trader backtest pair_trading \
    --tickers AMD,NVDA \
    --from 2023-01-01 --to today \
    --capital 100000 \
    --lookback 60 --entry-z 2.0 --exit-z 0.5 \
    --out results/pair_amd_nvda

# Same strategy, different pair — no code changes needed
python -m trader backtest pair_trading \
    --tickers KO,PEP \
    --from 2023-01-01 --to today \
    --out results/pair_ko_pep

# Grid-search a parameter range
python -m trader sweep pair_trading \
    --tickers AMD,NVDA \
    --from 2023-01-01 --to today \
    --lookback 30,45,60,90 --entry-z 1.5,2.0,2.5 \
    --out results/sweep_001

# Clear cache for one ticker (re-download next time)
python -m trader cache-clear TSLA
```

### Output structure

Each backtest writes one folder with:

- `result.json` — strategy, params, metrics (Sharpe, Sortino, max DD, Calmar, win rate, profit factor, total trades, avg duration), period, run timestamp
- `trades.csv` — one row per round-trip with side, ticker, size, price, reason
- `equity_curve.png` — portfolio value over time
- `drawdown.png` — underwater chart

## License

MIT (TBD).
