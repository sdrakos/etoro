# paper5 Gradient-Boosted-Trees (tabular) Model — Design

**Date:** 2026-06-09
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 3 (evolve), iteration 6: a non-deep, lower-capacity model.

## 1. Goal & scope

Every attention/deep form underperformed the plain LSTM (0.92), and the binding constraint is data,
not capacity — so the principled "instead of transformer" move is toward a **lower-capacity, strong-
inductive-bias** model. Gradient-boosted trees are the king of tabular problems: they handle the 10
features directly, are far less data-hungry than deep nets, and self-regularize. Build a **sklearn
HistGradientBoostingRegressor** on the same 10 features, evaluate it leak-free against the LSTM
(0.92) and the fixed rule (1.11) on combined-18.

> Does a tabular GBT beat / match / lose to the deep LSTM on this thin data?

**In scope:** a `gbt_model.py` (GBT grid + a leak-free GBT walk-forward producing positions); a driver
that compares fixed-rule / LSTM / GBT on combined-18 (both bands) and reports feature importances;
offline tests.

**Out of scope (future):** XGBoost/LightGBM proper, multi-seed (GBT is low-variance), the LLM-on-text
direction, the eToro engine, the paper.

## 2. Architecture

The GBT does not fit the torch `nested_walkforward`/`_train_fold` (no `make`/`cfg`/epochs), so it gets
its OWN leak-free walk-forward, but **reuses `evaluate()`** for the net-of-cost metrics — identical
to the DMN evaluation path. paper4 and the torch `train_eval.py` are untouched.

```
paper5/code/
  gbt_model.py     # GBT_GRID + gbt_positions(X, fwd, vol, folds, grid, warm) -> POS (N,T)
  run_dmn_gbt.py   # driver: fixed-rule / LSTM / GBT on combined-18, both bands; + feature importances
  tests/           # test_gbt_model.py
```

Reuse: `crypto_features.build`, `band_eval`, `costs`, `metrics`, `train_eval.evaluate` +
`train_eval.make_folds` + `train_eval.nested_walkforward` (for the LSTM baseline row),
`models.make_lstm`/`LSTM_GRID`, `combined_data.fetch_combined_daily`.

## 3. The GBT model + position mapping (`gbt_model.py`)

`HistGradientBoostingRegressor` predicts the **next-day return** from the 10 features (a regression
target). Predictions are mapped to a continuous position with the SAME vol-target + band sizing as the
fixed rule, so the comparison isolates **signal quality**, not sizing.

```python
GBT_GRID = [  # small grid; selected per fold by validation IR (like the DMN's cfg selection)
    {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 100, "l2_regularization": 1.0},
    {"max_iter": 300, "learning_rate": 0.03, "max_leaf_nodes": 31, "min_samples_leaf": 200, "l2_regularization": 1.0},
    {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 7,  "min_samples_leaf": 300, "l2_regularization": 2.0},
]
```

`gbt_positions(X, fwd, vol, fold_bounds, grid=GBT_GRID, warm=252) -> POS (N,T)`:

For each `(train_hi, test_hi)` in `fold_bounds`:
1. `vlo = int(warm + 0.8*(train_hi-warm))` (last 20% of train as validation).
2. Flatten `X[:, warm:vlo]` to rows `(samples, 10)` with target `fwd[:, warm:vlo]` flattened
   (drop non-finite rows). For each `cfg`: fit `HistGradientBoostingRegressor(random_state=0, **cfg)`,
   predict the validation rows `X[:, vlo:train_hi]`, build positions (below), compute validation
   `metrics.ann_ir(net_val, 252)` on the equal-weight portfolio of those positions vs `fwd` on the
   val span; keep the best-IR cfg.
3. Refit the best cfg on `X[:, warm:train_hi]` (all train). Predict the test span `X[:, train_hi:test_hi]`.
4. `s = std(train-prediction) + 1e-9` (leak-free scale, train only). For each test row's prediction
   `rhat`: `direction = tanh(rhat / s)`; `position = clip(direction * (0.15 / vol_shifted), -2, 2)`;
   then per-asset `ewm(span=5)` smoothing. Write into `POS[:, train_hi:test_hi]`.

`POS` is zero on the train warmup region (leak-free). `vol` is the annualized realized vol `(N,T)`
passed in from the driver (`ret.rolling(30).std()*sqrt(252)`, shifted 1 for causality). `evaluate()`
later applies the band + equal-capital `/N` + costs, exactly as for the DMN.

Position-mapping is factored into a helper `predict_to_position(pred_row, vol_row, scale)` (returns
the clipped vol-scaled tanh position) so it is unit-testable.

Determinism: `random_state=0` everywhere; GBT is low-variance, so a single run suffices (no
multi-seed needed here).

## 4. Evaluation & comparison (`run_dmn_gbt.py`)

Combined-18, leak-free, `net_returns(spread_bps=10)`, `ann_ir/newey_west_t/deflated_sharpe`, PPY=252,
band in {0.0, 0.3}. The driver:
- computes `vol (N,T)` from the real close;
- builds the GBT `POS` via `gbt_positions`, and the LSTM `POS` via `nested_walkforward(make_lstm, LSTM_GRID, ...)`;
- evaluates both at both bands + the fixed-rule baseline;
- prints the table and the **feature importances** (sklearn `permutation_importance` of a GBT refit on
  the full real panel, OR the native split-based importance — the 10 features ranked);
- saves `figures/fig_dmn_gbt.png` (net IR bars vs the 0.92 and 1.11 reference lines).

| model | band | net IR | NW-t | DSR | +2022 |
|-------|------|--------|------|-----|-------|
| fixed-rule | hard | ~1.11 | ... | ... | ... |
| LSTM-DMN | none/hard | ~0.92 | ... | ... | ... |
| **GBT** | none/hard | ... | ... | ... | ... |

**Success criterion:** GBT (better band) **net IR > 0.92 AND NW-t > 1.5 AND DSR > 0.8** -> tabular
beats deep. `~0.92` -> equivalent (simpler/steadier model preferred). `< 0.92` -> deep holds. Bonus:
`GBT > 1.11` -> first ML to beat the rule. Any outcome is the honest result; no tuning to force one.

## 5. Testing (offline, no network, no heavy training)

- `test_gbt_model.py`:
  - **shape + leak-free:** on a small synthetic `(N,T,F)`/`fwd`/`vol`, `gbt_positions` returns `(N,T)`,
    `POS[:, :first_train]` is all zeros, and values are finite and `|POS| <= 2`.
  - **position mapping:** `predict_to_position` returns 0 when the prediction is 0; is bounded by
    `2` in magnitude; flips sign with the prediction's sign.
  - **determinism:** two `gbt_positions` calls with the same inputs give identical `POS`.
- Heavy real training only in the driver.

## 6. Conventions

- sklearn `HistGradientBoostingRegressor` (already installed; no new dependency). Real data from
  cached `combined_close.npz`. No `Co-Authored-By`. Opus for any dispatched subagent. Code/figures
  English, commentary Greek. Figures `git add -f`. `random_state=0`. `paper4/` and the torch
  `train_eval` training functions untouched (we only call `evaluate`/`make_folds`/`nested_walkforward`).
