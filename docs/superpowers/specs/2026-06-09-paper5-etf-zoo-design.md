# paper5 model-zoo on the paper4 18-ETF universe — Design

**Date:** 2026-06-09
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — confirmation experiment (cross-study consistency).

## 1. Goal & scope

Test whether the **universe** decides the winner: paper4's LSTM beat the rules (IR 0.58 > 0.47) on a
diversified ETF basket; paper5's rule beat the ML (1.14-1.52 > 0.88-0.92) on a crypto-dominated one.
Run the **full paper5 model zoo** (rule / LSTM / pure-Transformer / gated attention / GBT) on the
**paper4 18-ETF universe** over deep Yahoo history, and compare. If the ML approaches/beats the rule
here (where trends are subtle and history is long), the "universe determines the winner" explanation
is confirmed; if the rule still dominates, the explanation is incomplete.

**In scope:** one integration driver that loads the 18 ETFs (deep Yahoo, cached), runs all five models
leak-free, and prints/plots the comparison. **Out of scope:** new models, eToro, the paper.

## 2. Locked decisions (from brainstorming)

- **Universe:** the 18 ETFs of `paper4/code/etf_universe.TICKERS` (SPY, QQQ, IWM, EFA, EEM, TLT, IEF,
  LQD, HYG, GLD, SLV, DBC, USO, UUP, VNQ, XLE, XLF, XLK).
- **Data:** deep Yahoo (~2007-2026, common window after `dropna(how="any")`), PPY=252.
- **Costs:** flat 10 bps (consistent with all other paper5 Yahoo runs — comparison is relative, ML vs rule).
- **Models:** rule, LSTM (`make_lstm`), pure-Transformer (`make_transformer`), gated attention
  (`make_gated_hybrid`), GBT (`gbt_positions`). Both bands (none/hard).
- **Pre-registered interpretation:** ML (LSTM/GBT/attention) IR `>=` or near the rule on ETFs (while it
  lost on crypto) -> confirms "universe decides". Rule still clearly best -> "universe" is only part of
  the story (the rule dominates our setup; paper4's ML edge came from its features/period too). No
  tuning to force an outcome.

## 3. Architecture

Zero new core code; one integration driver. paper4 and the torch training functions untouched.

```
paper5/code/run_etf_zoo.py
  - ETF = etf_universe.TICKERS (import from paper4/code)
  - close = crypto_data.fetch_crypto_daily(tickers=ETF, period="20y", cache_path=etf18_close.npz)
            (the loader already accepts a ticker list + cache path; yfinance handles ETF symbols)
  - X, fwd, dates_ms = crypto_features.build(close.dropna(how="any"))
  - vol (N,T) causal from close ; folds = make_folds(T, 252, 1500, 252)
  - POS: rule (inline) ; LSTM / pure-Tr / gated via nested_walkforward ; GBT via gbt_positions
  - evaluate(POS, fwd, dates_ms, test_idx, band, spread_bps=10, ppy=252) for band in {0, 0.3}
  - table (model x band: netIR / ann% / maxDD / DSR) + fig_etf_zoo.png
```

Reuse: `crypto_data.fetch_crypto_daily`, `crypto_features.build`, `models.{make_lstm, make_transformer,
make_gated_hybrid, LSTM_GRID, TRANSF_GRID, GATED_GRID}`, `gbt_model.gbt_positions`,
`train_eval.{make_folds, nested_walkforward, evaluate}`, `band_eval`, `metrics`,
`paper4/code/etf_universe.TICKERS`.

## 4. Comparison & testing

Table (Yahoo 18-ETF deep, leak-free, net @10bps):

| model | band | net IR | ann % | maxDD | DSR |
|-------|------|--------|-------|-------|-----|
| fixed-rule | none/hard | ... | ... | ... | ... |
| LSTM-DMN | none/hard | ... | ... | ... | ... |
| pure-Transformer | none/hard | ... | ... | ... | ... |
| gated attention | none/hard | ... | ... | ... | ... |
| GBT | none/hard | ... | ... | ... | ... |

ann% from the net stream; maxDD from `metrics.max_drawdown`; DSR `n_trials=len(grid)`. Save
`figures/fig_etf_zoo.png` (net IR bars). **No new unit tests** — every core component is already
tested; this is an integration driver run by the controller (heavy + first-run network), reusing the
cache afterward.

## 5. Conventions

- Deep Yahoo via the existing loader + npz cache (`etf18_close.npz`, committed with `git add -f`). No
  `Co-Authored-By`. Code/figures English, commentary Greek. Figures `git add -f`. `paper4/` and the
  torch training functions untouched (import/call only). Honest: 10 bps is conservative for ETFs; the
  comparison is relative (ML vs rule on the same costs).
