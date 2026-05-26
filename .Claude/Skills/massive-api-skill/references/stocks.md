# Stocks API Reference

46 endpoints. Organized by category. All examples assume `client = RESTClient()`.

## Table of contents

- [Tickers](#tickers) — discovery & metadata (4 endpoints)
- [Aggregate Bars (OHLC)](#aggregate-bars-ohlc) — historical prices (4)
- [Snapshots](#snapshots) — current state (4)
- [Trades & Quotes](#trades--quotes) — tick-level data (4)
- [Technical Indicators](#technical-indicators) — SMA, EMA, MACD, RSI (4)
- [Market Operations](#market-operations) — exchanges, hours, conditions (4)
- [Corporate Actions](#corporate-actions) — IPOs, splits, dividends (6)
- [Fundamentals](#fundamentals) — financials, ratios, short interest, float (7)
- [Filings & Disclosures](#filings--disclosures) — SEC EDGAR (8)
- [News](#news) — articles with sentiment (1)

---

## Tickers

### All Tickers — `client.list_tickers()`
Browse all supported tickers across asset classes.
```python
for t in client.list_tickers(market="stocks", active=True, limit=1000):
    print(t.ticker, t.name)
```
Filters: `market`, `exchange`, `cusip`, `cik`, `date`, `active`, `search`, `sort`, `order`.

### Ticker Overview — `client.get_ticker_details(ticker)`
Deep details for one ticker: industry, CIK, FIGI, market cap, branding (logos).
```python
details = client.get_ticker_details("AAPL")
print(details.market_cap, details.sic_description, details.branding.logo_url)
```

### Ticker Types — `client.get_ticker_types()`
List all asset classifications. Useful for filtering.

### Related Tickers — `client.get_related_companies(ticker)`
Peer/competitor list based on news + returns analysis.
```python
related = client.get_related_companies("NVDA")
for r in related:
    print(r.ticker)
# Returns: AMD, INTC, AVGO, QCOM, etc.
```

---

## Aggregate Bars (OHLC)

### Custom Bars — `client.list_aggs(ticker, multiplier, timespan, from_, to)`
The workhorse. OHLCV bars at any timeframe.
```python
# 1-minute bars for 2023
for agg in client.list_aggs("AAPL", 1, "minute", "2023-01-01", "2023-12-31", limit=50000):
    print(agg.timestamp, agg.open, agg.high, agg.low, agg.close, agg.volume)

# 1-day bars
daily = client.list_aggs("AAPL", 1, "day", "2024-01-01", "2024-12-31")

# 5-minute bars
five_min = client.list_aggs("AAPL", 5, "minute", "2024-01-01", "2024-01-31")
```
Valid timespans: `second`, `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year`.

**Important**: `from_` (with underscore) — `from` is a Python keyword.

### Daily Market Summary — `client.get_grouped_daily_aggs(date)`
All US stocks for one day in one call. Powerful for bulk analysis.
```python
all_stocks = client.get_grouped_daily_aggs("2024-12-30")
# Returns ~10,000 tickers' daily OHLCV
```

### Daily Ticker Summary — `client.get_daily_open_close_agg(ticker, date)`
Opening + closing + pre/after-hours for specific date.
```python
oc = client.get_daily_open_close_agg("AAPL", "2024-12-30")
print(oc.preMarket, oc.open, oc.close, oc.afterHours)
```

### Previous Day Bar — `client.get_previous_close_agg(ticker)`
Just yesterday's OHLC. Quick health check.
```python
prev = client.get_previous_close_agg("AAPL")
```

---

## Snapshots

Snapshots are real-time consolidated state. Reset 3:30 AM ET, repopulate from 4:00 AM ET.

### Single Ticker Snapshot — `client.get_snapshot_ticker(market_type, ticker)`
```python
snap = client.get_snapshot_ticker("stocks", "AAPL")
print(snap.last_trade, snap.day.volume, snap.prev_day.close)
```

### Full Market Snapshot — `client.get_snapshot_all(market_type)`
10,000+ tickers in one response.
```python
all_snaps = client.get_snapshot_all("stocks")
```

### Unified Snapshot — `client.list_universal_snapshots(ticker_any_of=[...])`
Multi-asset in single call (stocks + options + crypto + forex).
```python
snaps = client.list_universal_snapshots(ticker_any_of=["AAPL", "X:BTCUSD", "C:EURUSD"])
```

### Top Market Movers — `client.get_snapshot_direction("stocks", "gainers")`
Top 20 gainers or losers.
```python
gainers = client.get_snapshot_direction("stocks", "gainers")
losers = client.get_snapshot_direction("stocks", "losers")
```

---

## Trades & Quotes

### Trades — `client.list_trades(ticker, timestamp=...)`
Tick-by-tick.
```python
for trade in client.list_trades("AAPL", timestamp="2024-12-30", limit=50000):
    print(trade.price, trade.size, trade.exchange)
```

### Last Trade — `client.get_last_trade(ticker)`
Most recent trade.
```python
trade = client.get_last_trade("AAPL")
```

### Quotes — `client.list_quotes(ticker, timestamp=...)`
NBBO quotes (best bid/ask).
```python
for q in client.list_quotes("AAPL", timestamp="2024-12-30", limit=50000):
    print(q.bid_price, q.bid_size, q.ask_price, q.ask_size)
```

### Last Quote — `client.get_last_quote(ticker)`
```python
quote = client.get_last_quote("AAPL")
```

---

## Technical Indicators

All use same signature: `client.get_{indicator}(ticker, ...)`. Pre-computed server-side.

### SMA — `client.get_sma(ticker, timespan, window, ...)`
```python
sma = client.get_sma("AAPL", timespan="day", window=50, series_type="close")
for v in sma.values:
    print(v.timestamp, v.value)
```

### EMA — `client.get_ema(...)`
Same args as SMA. Weights recent prices heavier.

### MACD — `client.get_macd(ticker, short_window=12, long_window=26, signal_window=9, ...)`
```python
macd = client.get_macd("AAPL", timespan="day")
for v in macd.values:
    print(v.timestamp, v.value, v.signal, v.histogram)
```

### RSI — `client.get_rsi(ticker, window=14, ...)`
Overbought >70, oversold <30.

---

## Market Operations

### Exchanges — `client.get_exchanges()`
All known exchange codes, names, market types.

### Market Holidays — `client.get_market_holidays()`
Forward-looking only.

### Market Status — `client.get_market_status()`
Current open/closed state across markets.

### Condition Codes — `client.list_conditions()`
Trade/quote condition mappings (CTA, UTP, OPRA, FINRA).

---

## Corporate Actions

### IPOs — `client.list_ipos()`
Historical and upcoming IPOs from 2008.
```python
for ipo in client.list_ipos(ipo_status="pending"):
    print(ipo.ticker, ipo.issue_start_date, ipo.final_issue_price)
```

### Splits — `client.list_splits()`
Adjustment factors for historical price normalization.
```python
for s in client.list_splits(ticker="AAPL"):
    print(s.execution_date, s.split_from, s.split_to)
```

### Dividends — `client.list_dividends()`
```python
for d in client.list_dividends(ticker="AAPL"):
    print(d.ex_dividend_date, d.cash_amount, d.frequency)
```

### Ticker Events — `client.get_ticker_events(id)`
Symbol changes, rebranding (experimental).

---

## Fundamentals

### Balance Sheets — `client.list_balance_sheets(ticker)`
Point-in-time financial position.

### Cash Flow Statements — `client.list_cash_flow_statements(ticker)`
Operating, investing, financing flows.

### Income Statements — `client.list_income_statements(ticker)`
Revenue, expenses, net income.

### Ratios — `client.list_ratios(ticker)`
Daily-updated TTM ratios: P/E, P/B, ROE, ROIC, current ratio, debt ratios, etc.
**Critical for value screening.**

### Short Interest — `client.list_short_interest(ticker)`
Bi-weekly FINRA data.
```python
for si in client.list_short_interest(ticker="GME"):
    print(si.settlement_date, si.short_interest, si.short_interest_ratio)
```

### Short Volume — `client.list_short_volume(ticker)`
Daily off-exchange short sales from ATSs.

### Float — `client.get_float(ticker)`
Public free float (excludes insider, strategic, locked-up shares).

---

## Filings & Disclosures

SEC EDGAR data, parsed and AI-ready.

### EDGAR Index — `client.list_filings_index()`
Master index of all SEC filings — form type, date, CIK, accession number, document links.
```python
for f in client.list_filings_index(form_type="10-K", filing_date_gte="2024-01-01"):
    print(f.ticker, f.form_type, f.filing_date, f.document_url)
```

### 10-K Sections — `client.list_10k_sections(ticker)`
Plain-text Business + Risk Factors. AI-ready for LLM ingestion.

### 8-K Text — `client.list_8k_text(ticker)`
Material events (M&A, leadership changes, contracts).

### 13-F Filings — `client.list_13f_filings(cik)`
Institutional holdings (>$100M AUM funds, quarterly).

### Risk Factors — `client.list_risk_factors(ticker)`
Standardized, categorized risk disclosures across companies.

### Risk Categories — `client.get_risk_categories()`
Full taxonomy (primary/secondary/tertiary categories).

### Form 3 — `client.list_form_3(cik)`
Initial insider ownership.

### Form 4 — `client.list_form_4(cik)`
Insider transactions (purchases, sales, options, gifts).
```python
for f4 in client.list_form_4(ticker="TSLA"):
    print(f4.transaction_date, f4.transaction_code, f4.shares, f4.price)
```

---

## News

### News — `client.list_ticker_news(ticker, ...)`
Articles + sentiment + tickers extracted.
```python
for n in client.list_ticker_news("NVDA", order="desc", limit=100):
    print(n.published_utc, n.title, n.sentiment, n.publisher.name)
```
Fields available: `title`, `description`, `article_url`, `published_utc`, `tickers` (extracted),
`sentiment` (positive/negative/neutral), `sentiment_reasoning`.

**Powerful**: Combine with Claude API to enhance sentiment with qualitative analysis.

---

## Plan tier reference

| Endpoint category | Basic ($0) | Starter ($29) | Developer ($79) | Advanced ($199) |
|---|---|---|---|---|
| Tickers, Aggregates, Corp Actions, News, Financials, Short, Float, Filings | ✓ | ✓ | ✓ | ✓ |
| Snapshots | partial | ✓ | ✓ | ✓ |
| Trades & Quotes | — | ✓ | ✓ | ✓ |
| Technical Indicators | ✓ | ✓ | ✓ | ✓ |
| Real-time WebSocket | — | 15-min delayed | real-time | real-time |
| Historical depth | 2y | 5y | 10y+ | 20y+ |

Financials & Ratios are separate **$29/mo expansion** (can stack on Basic).

---

## Common workflow recipes

### Recipe: Get all stocks above $1B market cap
```python
big_caps = []
for t in client.list_tickers(market="stocks", active=True, limit=1000):
    details = client.get_ticker_details(t.ticker)
    if details.market_cap and details.market_cap > 1_000_000_000:
        big_caps.append(t.ticker)
```

### Recipe: Build candlestick DataFrame
```python
import pandas as pd
aggs = list(client.list_aggs("AAPL", 1, "day", "2024-01-01", "2024-12-31"))
df = pd.DataFrame([{
    "timestamp": pd.to_datetime(a.timestamp, unit="ms"),
    "open": a.open, "high": a.high, "low": a.low, "close": a.close,
    "volume": a.volume, "vwap": a.vwap,
} for a in aggs])
df.set_index("timestamp", inplace=True)
```

### Recipe: Daily earnings screener (combine fundamentals + news)
```python
# Get tickers with recent earnings
for n in client.list_ticker_news(ticker=None, limit=100, order="desc"):
    if "earnings" in (n.title or "").lower():
        ticker = n.tickers[0] if n.tickers else None
        if ticker:
            ratios = next(client.list_ratios(ticker=ticker), None)
            if ratios:
                print(ticker, ratios.price_to_earnings_ratio, n.sentiment)
```

### Recipe: Detect 50/200 SMA golden cross
```python
sma50 = client.get_sma("AAPL", timespan="day", window=50, series_type="close")
sma200 = client.get_sma("AAPL", timespan="day", window=200, series_type="close")
# Check if sma50 crossed above sma200 recently
```
