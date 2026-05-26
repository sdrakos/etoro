# Options API Reference

19 endpoints for OPRA options data. Same client patterns as stocks — but ticker format differs.

## Critical: Options ticker format

```
O:<UNDERLYING><YYMMDD><C|P><STRIKE×1000 zero-padded to 8>
```

Examples:
- `O:AAPL230616C00150000` = AAPL, exp 2023-06-16, Call, strike $150.00
- `O:SPY251219P00400500` = SPY, exp 2025-12-19, Put, strike $400.50
- `O:TSLA240119C00250000` = TSLA, exp 2024-01-19, Call, strike $250.00

The strike is **multiplied by 1000** and zero-padded to 8 digits.

## Endpoint categories

- [Contracts (reference)](#contracts) — discovery (3)
- [Aggregates](#aggregates) — OHLC bars (4)
- [Snapshots](#snapshots) — chain + per-contract state (3)
- [Trades & Quotes](#trades--quotes) (3)
- [Technical Indicators](#technical-indicators) — same as stocks (4)
- [Market Ops & Reference](#market-ops--reference) (2)

---

## Contracts

### List Contracts — `client.list_options_contracts(underlying_ticker, ...)`
Find available option contracts for an underlying.
```python
contracts = list(client.list_options_contracts(
    "AAPL",
    expiration_date_gte="2024-01-01",
    expiration_date_lte="2024-06-30",
    contract_type="call",
    strike_price_gte=150,
    strike_price_lte=200,
))
for c in contracts:
    print(c.ticker, c.strike_price, c.expiration_date, c.contract_type)
```

### Get Contract — `client.get_options_contract(options_ticker)`
Details for one specific contract.
```python
c = client.get_options_contract("O:AAPL230616C00150000")
print(c.underlying_ticker, c.strike_price, c.expiration_date, c.shares_per_contract)
```

### Ticker Details — `client.get_ticker_details(options_ticker)`
Reuses the stocks endpoint for metadata.

---

## Aggregates (OHLC bars)

### Custom Bars — `client.list_aggs(options_ticker, multiplier, timespan, from_, to)`
Same as stocks. Just pass the `O:...` ticker.
```python
for a in client.list_aggs("O:SPY251219C00650000", 1, "day", "2023-01-30", "2023-02-03"):
    print(a.timestamp, a.open, a.close, a.volume)
```

### Daily Open/Close — `client.get_daily_open_close_agg(options_ticker, date)`
### Previous Day — `client.get_previous_close_agg(options_ticker)`
### Daily Market Summary — does NOT exist for options (use chain snapshot instead)

---

## Snapshots

### Options Chain — `client.list_snapshot_options_chain(underlying, params={...})`
**The most powerful options endpoint.** Get entire chain with greeks, IV, OI, bid/ask in one call.
```python
chain = list(client.list_snapshot_options_chain(
    "AAPL",
    params={
        "expiration_date.gte": "2024-03-16",
        "expiration_date.lte": "2024-04-19",
        "strike_price.gte": 150,
        "strike_price.lte": 200,
        "contract_type": "call",
    },
))
for opt in chain:
    print(opt.details.ticker,
          opt.day.close, opt.last_quote.bid, opt.last_quote.ask,
          opt.greeks.delta, opt.greeks.theta, opt.greeks.vega,
          opt.implied_volatility, opt.open_interest)
```

### Single Option Snapshot — `client.get_snapshot_option(underlying, options_ticker)`
```python
snap = client.get_snapshot_option("AAPL", "O:AAPL230616C00150000")
print(snap.greeks, snap.implied_volatility, snap.open_interest)
```

### Unified Snapshot — `client.list_universal_snapshots(ticker_any_of=[...])`
Works for options too. Cross-asset.

---

## Trades & Quotes

### Trades — `client.list_trades(options_ticker, timestamp=...)`
```python
for t in client.list_trades("O:AAPL230616C00150000", timestamp="2024-12-30"):
    print(t.price, t.size, t.exchange, t.conditions)
```

### Last Trade — `client.get_last_trade(options_ticker)`

### Quotes — `client.list_quotes(options_ticker, timestamp=...)`
NBBO quotes per contract.

---

## Technical Indicators

Same signatures as stocks: `get_sma`, `get_ema`, `get_macd`, `get_rsi`. Apply to the options ticker.
```python
rsi = client.get_rsi("O:SPY251219C00650000", timespan="day", window=14)
```

---

## Market Ops & Reference

### Exchanges — `client.get_exchanges(asset_class="options")`
OPRA-specific venues.

### Condition Codes — `client.list_conditions(asset_class="options")`

---

## Workflow recipes

### Recipe: Find ATM (at-the-money) calls expiring this Friday
```python
from datetime import date, timedelta
import calendar

today = date.today()
# Find this Friday
days_until_friday = (calendar.FRIDAY - today.weekday()) % 7
friday = today + timedelta(days=days_until_friday)

# Get current stock price first
snap = client.get_snapshot_ticker("stocks", "AAPL")
spot = snap.last_trade.price

# Find ATM calls
chain = list(client.list_snapshot_options_chain("AAPL", params={
    "expiration_date": friday.isoformat(),
    "contract_type": "call",
    "strike_price.gte": spot * 0.98,
    "strike_price.lte": spot * 1.02,
}))
for opt in chain:
    print(opt.details.strike_price, opt.last_quote.bid, opt.last_quote.ask, opt.greeks.delta)
```

### Recipe: Build IV term structure
```python
# All ATM calls across expirations
expirations = ["2024-04-19", "2024-05-17", "2024-06-21", "2024-09-20", "2024-12-20"]
iv_curve = {}
for exp in expirations:
    chain = list(client.list_snapshot_options_chain("SPY", params={
        "expiration_date": exp,
        "contract_type": "call",
    }))
    atm = min(chain, key=lambda o: abs(o.details.strike_price - spot))
    iv_curve[exp] = atm.implied_volatility
```

### Recipe: Scan for unusual options activity
```python
# Get all contracts with high volume/OI ratio
chain = list(client.list_snapshot_options_chain("NVDA"))
unusual = [
    opt for opt in chain
    if opt.open_interest and opt.day.volume
    and opt.day.volume > opt.open_interest * 0.5  # vol > 50% of OI
]
for opt in sorted(unusual, key=lambda o: -o.day.volume)[:20]:
    print(opt.details.ticker, opt.day.volume, opt.open_interest)
```
