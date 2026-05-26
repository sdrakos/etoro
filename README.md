# etoro — Trading Strategy & Backtest Platform

Quantitative trading platform that integrates with the Massive.com (Polygon.io rebrand) market data API. Designed for solo development with a path to a TradingView-style UI.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Massive REST API wrapper (FastAPI, 104 endpoints) | ✅ shipped |
| **1** | **Strategy + backtest core (Python, backtrader)** | **🔨 in progress** |
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

Strategy-agnostic backtesting framework. Drop a `.py` under `trader/strategies/` and it auto-registers. First strategy: generic cointegration pair trading (any 2 tickers).

Design spec: `docs/superpowers/specs/2026-05-27-trader-phase1-backtest-core-design.md`

```bash
# (planned CLI — Phase 1 in progress)
python -m trader fetch AMD,NVDA --from 2015-01-01
python -m trader backtest pair_trading --tickers AMD,NVDA --from 2020-01-01 --to 2026-05-01
python -m trader strategies
```

## License

MIT (TBD).
