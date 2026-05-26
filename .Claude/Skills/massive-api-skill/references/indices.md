# Indices API Reference

13 endpoints for US indices (SPX, NDX, DJX, VIX, etc.).

## Ticker format

Index tickers use the `I:` prefix:
- `I:SPX` — S&P 500
- `I:NDX` — Nasdaq 100
- `I:DJI` — Dow Jones Industrial Average
- `I:VIX` — CBOE Volatility Index
- `I:RUT` — Russell 2000

## Endpoints

### List Tickers — `client.list_tickers(market="indices")`
Discover all available indices.

### Ticker Types — `client.get_ticker_types(asset_class="indices")`

### Aggregate Bars — `client.list_aggs("I:SPX", 1, "day", "2024-01-01", "2024-12-31")`
Same pattern as stocks. Values are index values, not prices.
```python
for a in client.list_aggs("I:SPX", 1, "day", "2024-01-01", "2024-12-31"):
    print(a.timestamp, a.close)  # No volume for indices
```

### Daily Open/Close — `client.get_daily_open_close_agg("I:SPX", "2024-12-30")`

### Previous Close — `client.get_previous_close_agg("I:SPX")`

### Single Snapshot — `client.get_snapshot_ticker("indices", "I:SPX")`

### Market Status / Holidays — same as stocks

### Technical Indicators — `get_sma`, `get_ema`, `get_macd`, `get_rsi` on `I:SPX` etc.
```python
spx_rsi = client.get_rsi("I:SPX", timespan="day", window=14)
```

## Notes

- **No trades or quotes** for indices (they're calculated values, not traded instruments)
- **No volume** in aggregate bars (only OHLC)
- For tradeable index exposure, use the ETF equivalent (SPY for SPX, QQQ for NDX, etc.) — those are stocks
- For options ON indices, those are options tickers (e.g. `O:SPX...`)

## Workflow recipe: Market regime detection
```python
# Use VIX + SPX trend to classify regime
vix_snap = client.get_snapshot_ticker("indices", "I:VIX")
spx_sma50 = client.get_sma("I:SPX", timespan="day", window=50)
spx_sma200 = client.get_sma("I:SPX", timespan="day", window=200)

regime = "risk_on" if vix_snap.value < 20 and spx_sma50 > spx_sma200 else "risk_off"
```
