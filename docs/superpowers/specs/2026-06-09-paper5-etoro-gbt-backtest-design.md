# paper5 eToro real-price backtest of the GBT model — Design

**Date:** 2026-06-09
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 5 (deploy/validate): real-price backtest on eToro candles.

## 1. Goal & scope

The tabular GBT was the best model on Yahoo (net IR 1.13, ties the rule). Now validate it on **real
eToro broker prices** with **real per-asset spreads** — the honest "does the edge survive on the
broker?" test. Full leak-free walk-forward (GBT / LSTM / fixed-rule) on eToro daily candles (~1000
bars, ~4 years).

> Does the GBT edge survive on real eToro prices and real spreads, vs the rule and the LSTM?

**In scope:** a read-only eToro backtest engine that resolves the 18-asset basket to eToro
instruments, fetches daily candles, builds the 10 features, runs GBT/LSTM/rule with a leak-free
walk-forward, charges **real per-asset eToro spreads**, and reports the comparison + a figure.

**Out of scope:** placing orders (READ-ONLY: candles + search + rates only), live signal/execute,
the eToro engine refactor, the paper.

## 2. Locked decisions (from brainstorming)

- **Full walk-forward on eToro prices** (train + evaluate on the same real eToro candles), not
  train-on-Yahoo/serve-on-eToro.
- **Real per-asset spreads** from the live `/api/v1/market-data/instruments/rates` bid/ask (the
  `etoro_cost_check` pattern), charged on per-asset turnover.
- **Universe = whichever of the 18 resolves on eToro and has candles** (crypto `BTC-USD`->`BTC` etc.;
  ETFs as-is; DBC expected missing). Print resolved + missing.
- **Models compared:** GBT, LSTM-DMN, fixed-rule, both bands.

## 3. Architecture

New engine module under `paper5/engine/`. **paper4 is imported, never modified** (read-only reuse of
its candle helpers + instrument map). The eToro client is the shared demo `get_server_client()`.

```
paper5/engine/etoro_gbt_backtest.py
  - resolve tickers -> eToro instrument ids (search)         [reuse paper4 instrument_map.resolve]
  - fetch ~1000 daily candles per id                         [reuse paper4 etoro_backtest.parse_candles/build_closes]
  - close (T,N) + dates -> DataFrame -> crypto_features.build -> X (N,T,10), fwd (N,T)
  - vol (N,T) causal from close
  - POS: gbt_model.gbt_positions ; train_eval.nested_walkforward(make_lstm,...) ; fixed-rule
  - fetch live per-asset spreads (/instruments/rates) -> spread_bps[j]
  - net_per_asset(W, fwd, spread_bps_vec) over both bands
  - metrics (ann_ir, newey_west_t, deflated_sharpe, durability), PPY from actual bars/year
  - print table (GBT/LSTM/rule x band) + resolved/missing + per-asset spreads ; save figure
```

Reuse: `paper4/engine/etoro_backtest.{parse_candles,build_closes}`, `paper4/engine/instrument_map.resolve`,
`back/etoro_api.server.get_server_client`, `paper5/code/{crypto_features,gbt_model,train_eval,band_eval,models}`,
`paper4/code/metrics`. The candle fetch double-nesting and `items[]` search quirks are already handled
by the paper4 helpers.

## 4. Per-asset net (`net_per_asset`)

paper4 `costs.net_returns` charges a SCALAR spread; eToro spreads differ a lot per asset (ETF ~few
bps, BTC/ETH ~32 bps), so the backtest uses a per-asset cost:

```python
def net_per_asset(W, fwd, spread_bps_vec, short_fin_annual=0.0):
    """W, fwd: (T,N) weights and next-bar returns. spread_bps_vec: (N,). Returns net stream (T,)."""
    gross = np.nansum(W * fwd, axis=1)
    turn = np.zeros_like(W)
    turn[0] = np.abs(W[0])
    turn[1:] = np.abs(W[1:] - W[:-1])
    cost = np.nansum(turn * (np.asarray(spread_bps_vec) / 1e4), axis=1)
    fin = (short_fin_annual / 1e4 / 252.0) * np.nansum(np.clip(-W, 0, None), axis=1)
    return gross - cost - fin
```

Flow per model/band: `W = band_eval.apply_band(POS.T, band) / N` (T,N); slice to the walk-forward
test rows; `net = net_per_asset(W_test, fwd.T[test], spread_bps_vec)`; metrics on the finite stream.
`PPY = len(dates) / ((dates[-1]-dates[0]).days) * 365` (handles the mixed crypto/ETF calendar).

## 5. Evaluation, comparison, success

Table (real eToro prices, real per-asset spreads, both bands):

| model | band | net IR | NW-t | DSR | maxDD |
|-------|------|--------|------|-----|-------|
| fixed-rule | none/hard | ... | ... | ... | ... |
| LSTM-DMN | none/hard | ... | ... | ... | ... |
| **GBT** | none/hard | ... | ... | ... | ... |

Also print: resolved tickers + ids, missing tickers, and the per-asset spread (bps). Save
`figures/fig_etoro_gbt_backtest.png` (net IR bars). **What we look for:** does the GBT (best band)
net IR stay clearly positive (NW-t > 1.5) on real prices, and how it compares to rule/LSTM on the
SAME broker. Real spreads (esp. crypto ~32 bps) may lower the numbers vs Yahoo's flat 10 bps — that
drop IS the finding. No tuning to force an outcome; whatever survives is the honest real-price result.

## 6. Testing (offline, no network)

- `net_per_asset`: zero turnover -> cost 0; a high spread on one asset lowers net correctly; output
  shape `(T,)`.
- `parse_candles` round-trip on a synthetic candle dict -> ascending `(date, close)`; a synthetic
  panel through `crypto_features.build` yields `(N,T,10)`.
- The live path (`resolve`, candle fetch, `/rates`, `run`) is integration (network) — exercised only
  by the driver, NOT in the offline suite.

## 7. Conventions

- READ-ONLY eToro (candles/search/rates; NO orders). Demo `get_server_client`. Secrets only in
  `back/.env` (never printed). No `Co-Authored-By`. Opus for any dispatched subagent. Code/figures
  English, commentary Greek. Figures `git add -f`. `random_state=0`. `paper4/` untouched (import only).
