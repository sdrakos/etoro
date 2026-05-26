# Common Patterns Reference

Cross-cutting patterns that apply across all Massive endpoints.

## Table of contents

- [Authentication](#authentication)
- [Pagination control](#pagination-control)
- [Filter operators](#filter-operators)
- [Timestamps](#timestamps)
- [Rate limiting & retries](#rate-limiting--retries)
- [Debug mode](#debug-mode)
- [Error handling](#error-handling)
- [WebSocket streaming](#websocket-streaming)
- [Flat Files (bulk S3)](#flat-files-bulk-s3)
- [Async support](#async-support)

---

## Authentication

```python
# Recommended: environment variable
import os
os.environ["MASSIVE_API_KEY"] = "your_key"  # or set in shell
from massive import RESTClient
client = RESTClient()  # reads from env automatically

# Alternative: hardcode (not recommended)
client = RESTClient("your_key_here")
```

Backward compat: `POLYGON_API_KEY` env var still works (old Polygon.io users).

---

## Pagination control

`list_*` methods return generators that auto-paginate.

### Default (auto-paginate everything)
```python
client = RESTClient()  # pagination=True is default
trades = list(client.list_trades("TSLA", limit=100))
# `limit` = page size. Iterator yields ALL trades, fetching 100 per page.
# Can return millions of records!
```

### Disable auto-pagination
```python
client = RESTClient(pagination=False)
trades = list(client.list_trades("TSLA", limit=100))
# Exactly 100 trades, stops there.
```

### Manual control with itertools
```python
from itertools import islice
client = RESTClient()  # pagination=True
first_500 = list(islice(client.list_trades("TSLA", limit=100), 500))
# Gets first 500 trades across multiple pages
```

**Performance tip**: Always use the **maximum supported `limit`** for the endpoint (often 50000 for aggs, 1000 for news, 100 for trades/quotes). Fewer pages = fewer API calls = faster.

---

## Filter operators

Many `list_*` endpoints accept filter parameters via `params={...}` dict. Supported operators:

| Operator | Meaning |
|---|---|
| `.gt` | greater than |
| `.gte` | greater than or equal |
| `.lt` | less than |
| `.lte` | less than or equal |

### Example: Options chain with multiple filters
```python
for opt in client.list_snapshot_options_chain("AAPL", params={
    "expiration_date.gte": "2024-03-16",
    "expiration_date.lte": "2024-06-21",
    "strike_price.gte": 150,
    "strike_price.lte": 200,
    "contract_type": "call",
}):
    print(opt.details.ticker)
```

### Example: News filtered by date
```python
for n in client.list_ticker_news("NVDA", params={
    "published_utc.gte": "2024-12-01",
    "published_utc.lte": "2024-12-31",
}):
    print(n.title)
```

Many endpoints also accept these as direct kwargs (e.g., `expiration_date_gte=...`) — both work.

---

## Timestamps

**All Massive timestamps are Unix nanoseconds (UTC).** Common pitfalls:

### Conversion
```python
import pandas as pd

# From aggregate bars (window_start or timestamp field)
dt_utc = pd.to_datetime(agg.timestamp, unit="ms")  # NOTE: aggs use ms, not ns!
dt_utc = pd.to_datetime(trade.sip_timestamp, unit="ns")  # trades/quotes use ns

# Convert to ET for market analysis
dt_et = dt_utc.tz_localize("UTC").tz_convert("America/New_York")
```

### Aggregate bars: `timestamp` is **milliseconds**
### Trades/Quotes: `sip_timestamp`, `participant_timestamp`, `trf_timestamp` are **nanoseconds**

```python
# In raw flat file CSVs
date = pd.to_datetime(row["window_start"], unit="ns").date()
```

### Market hours (always ET):
- Pre-market: 04:00–09:30 ET
- Regular: 09:30–16:00 ET
- After-hours: 16:00–20:00 ET

---

## Rate limiting & retries

### Free tier: 5 calls/min
```python
import time

def safe_call(fn, *args, **kwargs):
    """Wrapper for free-tier safety."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        if "rate" in str(e).lower():
            time.sleep(15)
            return fn(*args, **kwargs)
        raise

# Or just add 12s between calls
for ticker in tickers:
    data = client.get_aggs(ticker, 1, "day", "2024-01-01", "2024-12-31")
    time.sleep(12)
```

### Paid tier: high but not unlimited
```python
# Robust retry with exponential backoff
from time import sleep

def fetch_with_retry(fn, *args, max_attempts=5, **kwargs):
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            wait = 2 ** attempt
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s")
            sleep(wait)
    raise RuntimeError(f"Failed after {max_attempts} attempts")
```

For high-volume needs, prefer **Flat Files** (see below) over many REST calls.

---

## Debug mode

```python
client = RESTClient(trace=True, verbose=True)
# Prints full request URL, headers, response headers for every API call
```

Output example:
```
Request URL: https://api.massive.com/v2/aggs/ticker/TSLA/range/1/minute/2023-08-01/2023-08-01?limit=50000
Request Headers: {'Authorization': 'Bearer REDACTED', 'Accept-Encoding': 'gzip', ...}
Response Headers: {'X-Request-Id': '727c82feed3790...', ...}
```

**Pro tip**: Save `X-Request-Id` from response headers — useful when contacting Massive support.

---

## Error handling

Common exceptions:
- `BadResponse` — non-2xx status (rate limit, invalid API key, no data)
- `AuthError` — invalid/missing API key
- Connection errors (timeout, DNS)

```python
from massive.exceptions import BadResponse, AuthError

try:
    data = client.get_aggs("AAPL", 1, "day", "2024-01-01", "2024-12-31")
except AuthError:
    print("Check MASSIVE_API_KEY")
except BadResponse as e:
    print(f"API error: {e}")
except Exception as e:
    print(f"Network error: {e}")
```

---

## WebSocket streaming

For real-time data, use `WebSocketClient` instead of REST.

```python
from massive import WebSocketClient
from massive.websocket.models import WebSocketMessage
from typing import List

# Subscription format: <PREFIX>.<TICKER>
# T = Trades, Q = Quotes, A = Aggregate (1s), AM = Aggregate (1m)
# Star = all tickers: ["T.*"]

ws = WebSocketClient(
    api_key="your_key",  # or None to read MASSIVE_API_KEY env
    subscriptions=["T.AAPL", "T.TSLA", "Q.AAPL"],
    market="stocks",  # or "options", "crypto", "forex", "indices"
)

def handle_msg(msgs: List[WebSocketMessage]):
    for m in msgs:
        print(m)

ws.run(handle_msg=handle_msg)
```

### WebSocket subscription prefixes

**Stocks:**
- `T.TICKER` — trades
- `Q.TICKER` — quotes
- `A.TICKER` — aggregate per second
- `AM.TICKER` — aggregate per minute
- `LULD.TICKER` — limit up/limit down events
- `NOI.TICKER` — net order imbalance
- `XL.*` — level 2 book updates (paid)

**Options:** Same as stocks but with `O:...` tickers.

**Crypto:**
- `XT.X:BTCUSD` — trades
- `XQ.X:BTCUSD` — quotes
- `XL2.X:BTCUSD` — L2 book updates
- `XA.X:BTCUSD` — aggregate per second

**Forex:**
- `CA.C:EURUSD` — aggregates
- `C.C:EURUSD` — quotes

### Real-time tier requirements
- **Free / Basic**: 15-min delayed data only
- **Developer ($79+)**: real-time
- **Advanced ($199+)**: real-time + L2 + extended history

---

## Flat Files (bulk S3)

For massive historical downloads (years of tick data), **don't use REST** — use Flat Files (S3-compatible).

### Setup with MinIO client
```bash
mc alias set s3massive https://files.massive.com YOUR_ACCESS_KEY YOUR_SECRET_KEY

# Download all 2024 daily aggregates for US stocks
mc cp --recursive s3massive/flatfiles/us_stocks_sip/day_aggs_v1/2024/ ./data/

# Extract gzipped CSVs
gunzip ./data/**/*.gz
```

### Bucket structure
```
flatfiles/
├── us_stocks_sip/
│   ├── day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz
│   ├── minute_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz
│   ├── trades_v1/YYYY/MM/YYYY-MM-DD.csv.gz
│   └── quotes_v1/YYYY/MM/YYYY-MM-DD.csv.gz
├── us_options_opra/
└── global_crypto/
```

### Process CSV with pandas
```python
import pandas as pd
df = pd.read_csv("./data/2024-12-30.csv")
# Columns: ticker, volume, open, close, high, low, window_start (ns), transactions
df["date"] = pd.to_datetime(df["window_start"], unit="ns")
```

**Use Flat Files when:**
- Backtesting multi-year periods
- Building local databases (Supabase, ClickHouse)
- Tick-level analysis across many tickers
- Avoiding REST rate limits

**Use REST when:**
- Real-time / recent queries
- Specific filtered lookups
- Production app with on-demand data

---

## Async support

The `RESTClient` is synchronous. For async use cases, see `examples/tools/async_websocket_rest_handler/` in the GitHub repo or use `httpx`/`aiohttp` to call the REST endpoints directly with `Authorization: Bearer <key>` header.

---

## Custom raw GET (for unsupported endpoints)

If Massive adds an endpoint that's not yet in the SDK:
```python
result = client.get("/v3/some/new/endpoint", params={"foo": "bar"})
# Returns raw dict
```

Or for paginated endpoints:
```python
for item in client.list("/v3/some/new/endpoint", params={"foo": "bar"}):
    print(item)
```
