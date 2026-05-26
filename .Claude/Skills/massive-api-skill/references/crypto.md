# Crypto & Forex API Reference

Crypto: 20 endpoints. Forex: 19 endpoints. Same patterns, different ticker prefix.

## Ticker formats

- **Crypto**: `X:` prefix — `X:BTCUSD`, `X:ETHUSD`, `X:SOLUSD`, `X:DOGEUSD`
- **Forex**: `C:` prefix — `C:EURUSD`, `C:GBPJPY`, `C:USDCAD`

## Available endpoints (both)

| Endpoint | Crypto | Forex |
|---|---|---|
| Tickers | `list_tickers(market="crypto")` | `list_tickers(market="fx")` |
| Aggregates | `list_aggs("X:BTCUSD", ...)` | `list_aggs("C:EURUSD", ...)` |
| Grouped Daily | `get_grouped_daily_aggs(date, locale="global", market="crypto")` | `get_grouped_daily_aggs(date, locale="global", market="fx")` |
| Daily Open/Close | `get_daily_open_close_agg("X:BTCUSD", date)` | `get_daily_open_close_agg("C:EURUSD", date)` |
| Previous Close | `get_previous_close_agg("X:BTCUSD")` | `get_previous_close_agg("C:EURUSD")` |
| Trades (crypto only) | `list_trades("X:BTCUSD")` | — |
| Last Trade | `get_last_crypto_trade(from_, to)` | — |
| Quotes (forex only) | — | `list_quotes("C:EURUSD")` |
| Last Quote (forex) | — | `get_last_forex_quote(from_, to)` |
| Single Snapshot | `get_snapshot_ticker("crypto", "X:BTCUSD")` | `get_snapshot_ticker("forex", "C:EURUSD")` |
| All Snapshots | `get_snapshot_all("crypto")` | `get_snapshot_all("forex")` |
| Gainers/Losers | `get_snapshot_direction("crypto", "gainers")` | `get_snapshot_direction("forex", "gainers")` |
| L2 Book (crypto only) | `get_snapshot_crypto_book("X:BTCUSD")` | — |
| Real-time conversion (forex only) | — | `get_real_time_currency_conversion("USD", "EUR", amount=100)` |
| Exchanges | `get_exchanges(asset_class="crypto")` | `get_exchanges(asset_class="fx")` |
| Conditions | `list_conditions(asset_class="crypto")` | `list_conditions(asset_class="fx")` |
| Market Holidays / Status | same as stocks |
| Technical Indicators (SMA/EMA/MACD/RSI) | yes | yes |

## Examples

### Crypto: Bitcoin daily bars
```python
for a in client.list_aggs("X:BTCUSD", 1, "day", "2024-01-01", "2024-12-31"):
    print(a.timestamp, a.open, a.close, a.volume)
```

### Crypto: Level 2 order book
```python
book = client.get_snapshot_crypto_book("X:BTCUSD")
for bid in book.bids[:10]:
    print("BID", bid.price, bid.size)
for ask in book.asks[:10]:
    print("ASK", ask.price, ask.size)
```

### Forex: Real-time conversion
```python
result = client.get_real_time_currency_conversion("USD", "EUR", amount=10000, precision=2)
print(f"$10,000 = €{result.converted}")
```

### Forex: NBBO quotes
```python
for q in client.list_quotes("C:EURUSD", timestamp="2024-12-30", limit=50000):
    print(q.bid_price, q.ask_price, q.bid_exchange)
```

## Important differences from stocks

1. **24/7 markets** — no market open/close hours for crypto; forex closes weekends
2. **Global locale** — `locale="global"` instead of `locale="us"` for grouped queries
3. **No SEC filings, no fundamentals, no IPOs, no dividends** — only price/trade data
4. **Volume on crypto is exchange volume** (not consolidated like US stocks SIP feed)

## Workflow recipe: Crypto mean reversion screener
```python
# Find oversold crypto pairs
all_crypto = client.get_snapshot_all("crypto")
oversold = []
for snap in all_crypto:
    rsi = client.get_rsi(snap.ticker, timespan="day", window=14)
    if rsi.values and rsi.values[0].value < 30:
        oversold.append((snap.ticker, rsi.values[0].value, snap.todaysChangePerc))
oversold.sort(key=lambda x: x[1])
```
