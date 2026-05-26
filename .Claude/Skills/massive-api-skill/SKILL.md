---
name: massive-api
description: Complete Massive.com (formerly Polygon.io) market data integration for Python — REST + WebSocket for US stocks, options, indices, crypto, forex, treasury yields, news sentiment, and SEC EDGAR filings. Use ALWAYS when user mentions Massive.com, massive-api-client, Polygon.io (rebranded as Massive), polygon-python, stock market data API, options chain, OHLCV bars, technical indicators (SMA/EMA/MACD/RSI), tick trades/quotes, NBBO, dividends, splits, IPOs, 10-K/8-K/13-F/Form 4 filings, financial statements, short interest, free float, related companies, news sentiment, crypto/forex pairs, anomaly detection, or wants to build any trading bot/backtesting framework/data pipeline using Massive data. Also trigger for market data ingestion to Supabase, screeners, PEAD/SUE/EAR computation, multi-asset analytics, or programmatic US equity market access. Covers free tier, all paid plans, pagination, rate limiting, debug mode, vectorbt/pandas integration.
---

# Massive.com API Skill

## CRITICAL CONTEXT: Massive = Polygon.io rebrand

**Massive.com is the new name of Polygon.io** (rebrand: October 30, 2025). If the user mentions "Polygon.io", "polygon-api-client", or `polygon` Python package, they mean Massive. Existing API keys, integrations, and `api.polygon.io` endpoints still work — but new code should use:
- Package: `pip install -U massive`
- Import: `from massive import RESTClient, WebSocketClient`
- Base URL: `api.massive.com`
- Env variable: `MASSIVE_API_KEY` (was `POLYGON_API_KEY`)

## When to use this skill

Trigger immediately when the user wants to:
- Fetch stock/options/indices/crypto/forex prices, trades, quotes
- Compute technical indicators (SMA, EMA, MACD, RSI)
- Build market data pipelines, screeners, backtests
- Analyze SEC filings programmatically
- Track corporate actions (dividends, splits, IPOs)
- Detect anomalies (unusual volume, price moves)
- Find related/peer companies
- Stream real-time data via WebSocket

## Quick start (read this first)

```python
import os
from massive import RESTClient

# API key from env (recommended) or hardcoded
client = RESTClient()  # uses MASSIVE_API_KEY env var

# Basic patterns — choose one:

# 1. Single result (get_*)
aggs = client.get_aggs("AAPL", 1, "day", "2024-01-01", "2024-12-31")

# 2. Paginated iterator (list_*) — auto-paginates by default
for trade in client.list_trades("TSLA", limit=100):
    print(trade)  # fetches ALL trades, 100 per page

# 3. Disable auto-pagination if you want just N results
client = RESTClient(pagination=False)
trades = list(client.list_trades("TSLA", limit=100))  # exactly 100, stops
```

## API surface overview

Massive provides 9 product categories. For each, this skill has detailed reference docs:

| Category | What it covers | Reference file |
|---|---|---|
| **Stocks** | OHLCV, trades, quotes, technicals, fundamentals, filings, news | `references/stocks.md` |
| **Options** | OPRA options chains, trades, quotes, snapshots | `references/options.md` |
| **Indices** | Major US indices values & reference | `references/indices.md` |
| **Crypto** | Global crypto trades, quotes, aggregates | `references/crypto.md` |
| **Forex** | Currency pairs (similar pattern to crypto) | `references/crypto.md` (similar) |
| **Futures** | CME venues (less common, less developed) | `references/stocks.md` (pattern) |
| **Economy** | Treasury yields, macro indicators | `references/economy.md` |
| **Alternative** | News, sentiment | `references/alternative.md` |
| **Filings** | SEC EDGAR (10-K, 8-K, 13-F, Form 3, Form 4) | `references/filings.md` |

**Common workflow patterns** are in `references/patterns.md` — read this for filter operators (`.gte`, `.lte`), pagination control, debug mode, error handling.

## Decision tree: which reference to load

```
User mentions...                          → Load reference
────────────────────────────────────────────────────────────
"stock", "ticker", "OHLC", "SMA/EMA/RSI"  → stocks.md
"options chain", "strike", "expiration"   → options.md
"index", "SPX", "NDX"                     → indices.md
"crypto", "BTC", "ETH", "X:..."           → crypto.md
"forex", "FX", "currency pair", "C:..."   → crypto.md (similar pattern)
"treasury", "yield", "CPI", "macro"       → economy.md
"news", "sentiment", "headlines"          → alternative.md
"10-K", "8-K", "13-F", "insider"          → filings.md
"anomaly", "unusual volume", "scanner"    → patterns.md + scripts/anomaly_detector.py
"related", "peers", "competitors"         → scripts/related_companies.py
"WebSocket", "real-time stream"           → patterns.md (WebSocket section)
```

## Bundled scripts (production-ready)

The `scripts/` directory has working implementations:

| Script | Purpose | When to use |
|---|---|---|
| `anomaly_detector.py` | Detect unusual volume (z-score > 3) across all stocks for a given date | Build daily scanners |
| `related_companies.py` | Build network graph of related tickers | Peer analysis, portfolio diversification |
| `historical_ingest.py` | Download historical OHLCV to Supabase/CSV | Backtesting data pipeline |
| `pead_data_pipeline.py` | Compute SUE/EAR from earnings + price data | PEAD strategy implementation |
| `multi_asset_snapshot.py` | Get unified snapshot across stocks/options/crypto | Cross-market monitoring |

Read the script, then adapt — don't run blindly without understanding it.

## Critical patterns to remember

### Pattern 1: `get_*` vs `list_*`
- `get_*` returns single result/object → use for "give me one thing"
- `list_*` returns generator with auto-pagination → use for "give me all matching X"

### Pattern 2: Filter operators
For `list_*` endpoints, use these operators in `params={...}`:
- `.gt` (greater than)
- `.gte` (greater than or equal)
- `.lt` (less than)
- `.lte` (less than or equal)

Example:
```python
for opt in client.list_snapshot_options_chain("AAPL", params={
    "expiration_date.gte": "2024-03-16",
    "strike_price.gte": 150,
    "strike_price.lte": 200,
}):
    print(opt)
```

### Pattern 3: Ticker prefixes (asset class)
| Asset | Format | Example |
|---|---|---|
| US Stock | `TICKER` | `AAPL` |
| Crypto | `X:PAIR` | `X:BTCUSD` |
| Forex | `C:PAIR` | `C:EURUSD` |
| Options | `O:UNDERLYING_YYMMDD_C/P_STRIKE` | `O:AAPL230616C00150000` |
| Index | `I:NAME` | `I:SPX` |

### Pattern 4: Rate limits
- **Free tier**: 5 calls/min — easy to hit, add `time.sleep(12)` between calls
- **Starter ($29/mo)**: unlimited but with fair use
- For bulk historical: prefer **Flat Files** over REST (S3-compatible, MinIO client)
- Always use `limit=50000` (max) for `list_*` to minimize API calls

### Pattern 5: Timestamps
All Massive timestamps are **Unix nanoseconds (UTC)**. Convert carefully:
```python
import pandas as pd
date = pd.to_datetime(row["window_start"], unit="ns").date()
```
For ET-aligned analysis (market hours 9:30-16:00 ET), explicitly convert UTC → America/New_York.

### Pattern 6: Debug mode
When something breaks, enable trace:
```python
client = RESTClient(trace=True, verbose=True)
# Prints request URL, headers, response headers for every call
```

## Common mistakes to avoid

1. **Forgetting `from_` (with underscore)** in `list_aggs` — `from` is a Python keyword
2. **Using `get_*` when you wanted `list_*`** — get returns one record/object, list iterates pages
3. **Not converting nanosecond timestamps** — `window_start` is ns, not seconds or ms
4. **Mixing up adjusted vs unadjusted prices** — for backtesting splits/dividends, use `adjusted=True`
5. **Hitting rate limits on free tier** — add sleeps or upgrade
6. **Hardcoding API keys** — always use `MASSIVE_API_KEY` env var
7. **Treating timezone as ET** — data is UTC, market times are ET, must convert explicitly

## Integration with other tools

- **Supabase/PostgreSQL**: see `scripts/historical_ingest.py` for batch insertion pattern
- **vectorbt**: `client.list_aggs()` returns objects with `.timestamp`, `.open/high/low/close/volume` — easy to convert to DataFrame
- **pandas**: `df = pd.DataFrame([a.__dict__ for a in aggs])`
- **WebSocket**: see `references/patterns.md` for live streaming setup
- **Claude API for sentiment**: combine `client.list_ticker_news()` outputs → Claude → store qualitative scores

## Available endpoint counts (for capacity planning)

| Category | Endpoints |
|---|---|
| Stocks | 46 |
| Options | 19 |
| Crypto | 20 |
| Forex | 19 |
| Indices | 13 |
| Futures | 9 |
| Economy | 4 |
| Alternative | 2 |
| Partners | 15 |

## Next steps in user workflow

After reading this skill, typically:
1. **Confirm API key setup** — does user have `MASSIVE_API_KEY`?
2. **Identify use case** → load the right reference file
3. **Start with examples** — copy from `scripts/` and adapt
4. **For trading systems**: combine with PEAD/momentum/value frameworks
5. **For production**: add error handling, retries, rate limit backoff
