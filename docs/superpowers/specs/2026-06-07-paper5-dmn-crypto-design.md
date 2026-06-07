# paper5 DMN build (crypto daily, LSTM + Momentum Transformer) — Design

**Date:** 2026-06-07
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phases 2 (reproduce/critique) + 3 (evolve), on the proven banded-crypto core.

## 1. Goal & scope

Run an honest, leak-free experiment: build a Deep Momentum Network (LSTM) **and** a
Momentum Transformer (attention) on the **crypto daily** basket, using the **paper4 10-feature
set**, and answer one question:

> Does the ML model — net of real eToro costs (10 bps) and with our no-trade band — beat the
> fixed-rule banded core (net IR 1.27, NW-t 2.74, positive in 2022)?

If yes → the ML lifts the gross edge of the production-viable core. If no → **honest null**,
written up plainly (cf. paper3). We do not reframe a null as a win.

**In scope:** crypto daily only; LSTM DMN; Momentum Transformer; no-trade band ablation; nested
walk-forward + Deflated Sharpe; net-of-cost evaluation; offline tests; a comparison driver +
figure.

**Out of scope (future specs):** eToro live engine (signal/execute/backtest on real candles);
4h / multi-timeframe; ETF basket; the journal paper and business report.

## 2. Architecture

Approach A: **reuse paper4 as a library, add new paper5 modules.** paper5 imports `paper4/code`
via `sys.path` (the pattern already used by `paper5/code/make_crypto_pnl_figure.py`) and adds only
its own modules. **paper4 is never modified** (a parallel session runs from there).

```
paper5/code/
  crypto_data.py     # fetch 8 crypto daily (yfinance, auto_adjust), shared basket
  crypto_features.py # wrap paper4 build_features -> X (N,T,10), fwd (N,T)
  models.py          # DeepMomentumNetwork (LSTM, paper4) + MomentumTransformer (new)
  band_eval.py       # apply_band() at serve + the band ablation
  train_eval.py      # nested WF (paper4) + Deflated Sharpe + net@10bps + durability
  run_dmn_crypto.py  # driver: produces the comparison table + figure
  tests/             # offline tests (small synthetic tensors, no network)
```

Reused from paper4 (import, do not copy): `features.build_features`, `dmn.sharpe_loss`,
`dmn.nested_walkforward`, `dmn.DeepMomentumNetwork`, `costs.net_returns`, `metrics.ann_ir`,
`metrics.newey_west_t`, `metrics.deflated_sharpe`, `metrics.durability_by_year`. The Kalman LLT /
BOCPD features (7–10) are pulled in transitively by `build_features` from
`Strategies/slow-momentum-fast-reversion/{kalman_llt,bocpd}.py`.

## 3. The two models (`models.py`)

Both take input `X (N,T,F=10)` and emit positions `(N,T)` in `[-1,1]` (tanh), trained with the
**same** `sharpe_loss` (portfolio Sharpe net of turnover) under the **same** nested walk-forward.
Only the sequence encoder differs — this keeps the LSTM-vs-attention comparison fair.

- **LSTM DMN** — reused unchanged from paper4 (`dmn.DeepMomentumNetwork`): one shared LSTM applied
  per asset over its own feature sequence → `tanh` head. Grid over `(hidden, weight_decay, dropout)`.
- **MomentumTransformer (new)** — causal Transformer encoder, same I/O and loss:
  `Linear(10 -> d_model)` -> sinusoidal positional encoding -> 1 `nn.TransformerEncoderLayer`
  (configurable, default 1 layer) with a **causal mask** (position t attends only to <= t, so it is
  leak-free) -> `Dropout` -> `tanh(Linear(d_model -> 1))`. Low capacity by design
  (`d_model` default 16, `nheads` default 2, 1 layer) because crypto daily is only ~4000 bars.
  Grid over `(d_model, nheads, dropout)`.

Both expose the same constructor signature shape `Model(n_features, **cfg)` and `forward(x)` so
`train_eval` is model-agnostic.

## 4. Data flow & the ablation matrix

```
crypto_data.fetch()        -> close (T, N)
  -> crypto_features.build  -> X (N,T,10), fwd (N,T)
  -> train_eval.walk(model) -> raw OOS positions POS (N,T)   [leak-free]
  -> band_eval.apply_band(POS, band)  for band in {0.0 (none), 0.3 (hard)}
                            -> weights W (N,T)  (equal-capital: / N)
  -> costs.net_returns(W, fwd, spread_bps=10) -> net stream
  -> metrics: ann_ir, newey_west_t, deflated_sharpe, durability_by_year
```

The driver emits the honest ablation table (one row per model x band, plus the baseline):

| Model            | Band | net IR | NW-t | DSR | +2022? |
|------------------|------|--------|------|-----|--------|
| fixed-rule       | hard | 1.27   | 2.74 | ... | yes (baseline, reproduced) |
| LSTM DMN         | none | ...    | ...  | ... | ...    |
| LSTM DMN         | hard | ...    | ...  | ... | ...    |
| MomentumTransf.  | none | ...    | ...  | ... | ...    |
| MomentumTransf.  | hard | ...    | ...  | ... | ...    |

This isolates three effects independently: what the **band** adds, what the **ML** adds, what the
**attention** adds.

### The no-trade band (decisive lever)

`apply_band(pos, band)` is per-asset hysteresis: hold the current position; only switch to the
model's new target when `|target - current| > band`. Mechanism: it does not change *what* the model
predicts, only *how often* cost is paid. `break-even ~= gross / turnover`; the band cuts turnover
~35x (0.07 -> 0.002), pushing break-even from ~5 bps to >80 bps — above the ~10 bps eToro crypto
spread, which is exactly why the crypto core survives net of costs.

## 5. Evaluation & success criterion (`train_eval.py`)

- **Leak-free nested walk-forward** (paper4 `nested_walkforward`): increasing-train folds; per fold,
  config chosen on a validation split that never touches the test span; early-stop on the same
  validation.
- **Net of costs is mandatory:** `costs.net_returns(W, fwd, spread_bps=10)`.
- **Metrics:** `ann_ir` (net IR), `newey_west_t` (autocorrelation-robust t), `deflated_sharpe`
  (`n_trials` = number of configs tried, anti-overfit penalty), `durability_by_year` (the 2022 test).
- **"Worth it" criterion:** the ML model (LSTM or Transformer) **with hard band** must beat the
  fixed-rule baseline: **net IR > 1.27 AND NW-t > 2 AND DSR > 0 AND positive 2022**. If not met →
  **honest null**, reported as-is.

## 6. Testing (`tests/`, fully offline, no network)

Bare-import convention (run `pytest` from `paper5/code/`, like paper4):

- `test_features.py` — synthetic close with a known trend: the 5 multi-horizon returns have the
  correct sign; `X` shape is `(N,T,10)`; no NaN/inf after build.
- `test_band.py` — the worked example (band=0.3, start +0.50, targets [.60,.70,.85,.80]) yields
  exactly 1 switch not 4; `band=0` reproduces the input unchanged.
- `test_models.py` — LSTM and Transformer: input `(N,T,10)` -> output `(N,T)` within `[-1,1]`;
  **causal check** for the Transformer (perturbing a future timestep's input does not change a past
  output -> leak-free).
- `test_train_eval.py` — on a tiny synthetic tensor, nested-WF fills only the test spans (zeros
  elsewhere), no train->test leakage; `deflated_sharpe` returns a finite number.

Heavy real training (~4000 bars) lives only in the driver `run_dmn_crypto.py`, never in tests, so
tests stay fast and deterministic.

## 7. Conventions

- Train on Yahoo (yfinance, `auto_adjust=True`); serve on eToro later (out of scope here).
- Crypto basket = the 8 names already used: `BTC-USD, ETH-USD, SOL-USD, BNB-USD, XRP-USD, ADA-USD,
  LTC-USD, DOGE-USD`.
- No `Co-Authored-By` in commits. Opus for any dispatched subagent. Code/figures English; commentary
  Greek. Figures committed with `git add -f` (global `*.png` ignore).
- Determinism: `torch.manual_seed(0)` (already in paper4 `_train_fold`); no `Date.now`/random in
  tests.
```
