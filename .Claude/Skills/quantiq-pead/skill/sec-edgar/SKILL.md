---
name: sec-edgar
description: >-
  Pull free, point-in-time fundamental data from the SEC EDGAR REST APIs (data.sec.gov) and
  turn it into backtest-safe quant signals. Use this skill WHENEVER the user mentions SEC
  EDGAR, EDGAR API, data.sec.gov, company filings, 10-K / 10-Q / 8-K, XBRL, company facts,
  CIK lookup, point-in-time fundamentals, earnings, EPS, earnings surprise, SUE, PEAD,
  post-earnings-announcement drift, fundamental factors (value / quality / growth / accruals),
  or wants to fetch US company financials programmatically, build a fundamentals time series,
  or align fundamentals with daily stock prices for a trading model. Trigger even if they
  only say "get the earnings/financials for these tickers" or "where do I get free
  point-in-time fundamentals" — EDGAR is the answer and this skill is how to use it correctly.
---

# SEC EDGAR — free, point-in-time fundamentals for quant signals

EDGAR (Electronic Data Gathering, Analysis, and Retrieval) is the SEC's public archive where
every US-listed company is legally required to file its financials. It exposes free REST APIs
(`https://data.sec.gov`, no API key) that return structured XBRL data. For a quant, EDGAR's
killer property is that every fact carries its **filing date** — so the data is *point-in-time
by construction*, which is exactly what stops look-ahead bias in a backtest. Vendors like FMP
and Polygon ultimately source from here; EDGAR is the free, original layer.

## What you can DO and GET

- **Resolve tickers → CIK** (the SEC's company id), 10-digit zero-padded.
- **Company Facts** — every XBRL fact a firm ever filed, in one JSON.
- **Company Concept** — one line item over time (e.g. diluted EPS), efficiently.
- **Submissions** — full filing history with form types and filing dates.
- **Frames** — one fact across *all* companies for a period (instant cross-section).
- **Build signals**: point-in-time fundamental time series aligned to daily prices, and from
  them PEAD/SUE, value, quality, growth, accruals, investment, buyback signals.

## Access rules — read before any request
1. **User-Agent header with your name + email is mandatory** (e.g. `Stefanos Drakos stefanos@agelai.gr`). Missing → HTTP 403.
2. **≤ 10 requests/second** total; back off on 403/429/5xx, or you get IP-blocked.
3. CIK is **10-digit zero-padded** in URLs (`320193` → `CIK0000320193`).
4. XBRL structured data starts **~2009–2011**; earlier filings are HTML/text only.

The bundled client enforces (1)–(3) for you. Full endpoint table, fact fields, and bulk-download
URLs are in `references/endpoints.md`. Common XBRL tags per signal are in `references/xbrl_tags.md`.

## Environment note
`data.sec.gov` is **not reachable from the Claude analysis sandbox** (its network is limited to
package repositories). Run these scripts on the **user's machine**, where `requests` + a valid
User-Agent is all that's needed. In-sandbox, you can still read/edit the code and explain usage.

## Scripts (in `scripts/`)
Run from inside `scripts/` (or add it to `sys.path`). They need only `requests` and `pandas`.

### 1. `edgar_client.py` — the core client
```python
from edgar_client import EdgarClient
ec = EdgarClient("Your Name your@email.com")     # User-Agent is required

ec.cik_for("AAPL")                               # '0000320193'
ec.company_facts("AAPL")                         # everything (dict)
ec.concept_series("AAPL", "EarningsPerShareDiluted")   # tidy DataFrame w/ 'filed' dates
ec.submissions("AAPL")                           # filing history (dict)
ec.frames("Revenues", "CY2023Q4", "USD")         # all companies, one period
ec.available_tags("AAPL")                        # which tags this firm actually reports
```
`concept_series(..., keep=...)`: `'first_filed'` (as-first-reported — correct for event timing),
`'last_filed'` (restated), or `'all'`.

### 2. `fundamentals_loader.py` — many tickers → point-in-time panel
```python
from fundamentals_loader import load_concept_panel, to_pointintime_daily, quarterly_eps
panel = load_concept_panel(ec, ["AAPL","MSFT"], "revenue")   # long tidy table
daily = to_pointintime_daily(panel, calendar=my_trading_days)  # wide daily, ffilled from 'filed'
eps   = quarterly_eps(ec, ["AAPL","MSFT"])    # clean quarterly EPS (Q4 derived from 10-K)
```
`to_pointintime_daily` is the bridge from sparse quarterly facts to your daily price grid:
each value turns on at its **filing date** and holds until the next filing — no look-ahead.

### 3. `sue_pead.py` — the PEAD signal, with NO analyst data
The classic post-earnings-announcement drift uses a time-series earnings expectation
(Foster 1977; Bernard & Thomas 1989), so you do **not** need (expensive) analyst consensus:
`SUE = (EPS_t − EPS_{t−4}) / std(year-over-year changes)`.
```python
from sue_pead import build_pead_signal
signal = build_pead_signal("Your Name your@email.com",
                           tickers=my_universe,
                           calendar=my_trading_days,
                           hold_days=60, exec_lag=1)   # daily (date x ticker) signal
```
Entered with a **T+1 lag** after the filing date and held over the drift window. The output is a
cross-sectionally standardized daily frame that drops straight into a cross-sectional backtest
(e.g. a `load_panel`/feature seam).

### 4. `combine_signals.py` — merge many weak signals by RISK PARITY
The edge is breadth: several weak, orthogonal signals combined so each contributes EQUAL RISK
(not equal capital). Nothing is "learned", so no overfitting.
```python
from combine_signals import combine
# each value is a (date x ticker) signal frame (e.g. own PEAD + peer lead-lag + value...)
final, weights = combine({"own_pead": pead_sig, "peer_leadlag": leadlag_sig},
                         returns=daily_next_returns,   # optional: measures real signal risk
                         method="inverse_vol")          # or "erc" (correlation-aware) / "equal"
```
Each signal is z-scored per day, then weighted by `1/volatility` (a noisy signal gets less
weight, a steady one more) and summed. With `method="erc"` the weighting also accounts for
the correlation between signals (equal risk contribution). `final` is the (date x ticker) score
you rank and trade. When two signals disagree on a name, its combined score is muted — two
orthogonal sources cross-checking each other.

### 5. `gate.py` — keep only signals with real, durable edge (utility-weighted)
Judge each signal by the risk-adjusted P&L of its long-short portfolio (weight x return =
economic utility, Jane-Street-style), with Newey-West inference and an early-vs-late split
for decay. A signal PASSES only if utility is positive, significant (|NW t| ≥ threshold),
and not collapsing late.
```python
from gate import gate
table, passed = gate({"own_pead": s1, "peer_leadlag": s2}, next_day_returns, t_thresh=2.0)
```

### 6. `regime.py` — the risk brake (volatility targeting)
Does NOT predict direction; it sizes the book down in stormy regimes and up in calm ones
(vol clustering is predictable; returns are not). Look-ahead-safe (uses only past vol).
```python
from regime import apply_regime
scaled_ret, exposure_mult = apply_regime(port_ret, market_or_book_state,
                                         mode="vol_target", target_vol=0.10)
```

### 7. `engine.py` — the whole pipeline in one runner
`signals -> gate -> risk-parity combine -> regime layer -> book`.
```python
from engine import build_signals, run
signals = build_signals(events, group_map, calendar, tickers, hold=60)  # own_pead + peer_leadlag
res = run(signals, next_day_returns, target_vol=0.10, market_state=market_returns)
```
`python engine.py --selftest` validates the full chain on synthetic data (known signal + a
vol regime with a crisis): the gate filters, risk parity combines survivors, and the brake
cuts drawdown while keeping risk-adjusted return — proving the wiring before you add real data.

## Signal-building workflow (the honest path)
1. Pick an **as-traded** universe (avoid survivorship bias — don't use only today's index members).
2. Pull the concept(s) you need with `concept_series` / `load_concept_panel`, keeping `filed` dates.
3. Convert to a **point-in-time daily panel** aligned to your trading calendar (`to_pointintime_daily`).
4. Build each signal (start with `sue_pead.py`; add value/quality/accruals from `references/xbrl_tags.md`).
5. Cross-sectionally rank/standardize, then **combine several orthogonal signals via risk parity**
   (`combine_signals.py`, `method="inverse_vol"` or `"erc"`) — no single fundamental signal is
   strong; the edge (if any) is breadth.
6. Evaluate with strict walk-forward + CPCV + Deflated Sharpe, and report the **decay rate**, not
   just the IR level. A null is a valid, publishable result — say so plainly.

## Critical correctness rules (these silently break backtests)
- **Align on `filed`, never on period `end`.** This is the whole point of using EDGAR.
- **Dedup deliberately**: `first_filed` for signal timing, `last_filed` only for restated analysis.
- **Handle tag inconsistency** with fallbacks / `available_tags`.
- **Derive Q4 EPS** (FY − Q1..Q3); prefer `NetIncomeLoss`/shares for rigor.
- **Respect the rate limit**; for many names use the bulk ZIPs (see `references/endpoints.md`).
- The model's job on filings text is to extract **numeric, point-in-time features** (e.g. a
  sentiment score for a quarter), **not** to make buy/sell judgments — narrative "analysis"
  invites look-ahead (the model knows the future) and isn't testable.
