# paper5 Synthetic-Daily Pretraining for Attention — Design

**Date:** 2026-06-07
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 3 (evolve), iteration 4 on the crypto+ETF DMN build.

## 1. Goal & scope

Across three iterations, attention never beat the plain LSTM (pure 0.07, naive hybrid -0.57, gated
0.29, frozen 0.39 vs LSTM 0.92): the binding constraint is **data** (only ~3000 daily bars / ~12
years), and attention is data-hungry. This iteration removes the data-starvation **for pretraining
only**, while keeping an honest, regime-proven evaluation on the real daily data:

> Does attention finally add value if we pretrain it on unlimited, perfectly-diversified synthetic
> daily data and then fine-tune on the real basket?

Pretrain the gated hybrid on a **parametric** synthetic dataset (so there is no leakage of real
data), warm-start the real model from it (gate reset to 0), and fine-tune per fold. A
**random-walk-pretrain control** is the honesty check: synthetic that contains NO signal must not
produce a "win", or the structured synthetic merely injected the answer.

**In scope:** a synthetic daily generator (structured + random-walk control); a pretrain function and
a warm-start trainer; a driver running the four-row ablation (LSTM / gated-no-pretrain /
gated+structured-pretrain / gated+randomwalk-pretrain) on the real combined-18 basket, both bands;
offline tests; a figure.

**Out of scope (future):** hourly data, ^VIX regime feature, the eToro engine, the paper.

## 2. Locked decisions (from brainstorming)

- **Synthetic universe = N=18 INDEPENDENT (uncorrelated) series**, N matched to the real basket so the
  portfolio-Sharpe loss has the same cross-section structure. Uncorrelated => ENB ~ 18 (perfect
  diversity), which is the proven lever (the LSTM went 0.07->0.92 on ENB 2.6->6.1). The generator
  draws each series independently.
- **Parametric generator (not block-bootstrap of real data)** => the synthetic is independent of the
  real OOS => pretraining cannot leak the test set.
- **Warm-start all weights, reset the gate to 0** at fine-tune (the chosen transfer): the model
  starts fine-tuning as an LSTM (gate 0) but with a pretrained attention machinery ready to switch on.
- **Evaluate ONLY on the real combined-18 daily OOS, net @10bps, PPY=252**, vs LSTM 0.92. Synthetic is
  pretraining-only; the honest, regime-testable (incl. 2022) evaluation is unchanged.

## 3. Architecture

Extend the existing paper5 modules (paper4 untouched).

```
paper5/code/
  synth_data.py        # make_synthetic(kind, n_assets, T, seed) -> (T,N) independent series
  train_eval.py        # + pretrain_model(...), + make_pretrained_trainer(state)
  run_dmn_pretrain.py  # driver: LSTM / gated / gated+structured / gated+randomwalk on real combined-18
  tests/               # extend test for synth_data + pretrain
```

Reuse: `crypto_features.build` (same 10 features on synthetic closes), `combined_data`,
`band_eval`, `costs`, `metrics`, `GatedHybridMomentumNetwork`/`make_gated_hybrid`/`GATED_GRID`,
`nested_walkforward` (its `trainer=` hook), `_train_fold`/`_prep_tensors`/`_run_epochs`.

## 4. Synthetic generator (`synth_data.py`)

`make_synthetic(kind, n_assets=18, T=6000, seed=0) -> pandas.DataFrame (T, n_assets)` of **mutually
independent** daily close series (a synthetic business-day index; values start at 100). Determinism
via `numpy.random.default_rng(seed)`.

- `kind="structured"`: each series is an independent random mix of regimes — drift/trending
  segments, mean-reverting (Ornstein-Uhlenbeck) segments, volatility clustering (a simple
  GARCH-like vol process), and occasional jumps / changepoints. Per-series parameters are drawn
  randomly so the 18 series are diverse and uncorrelated. Teaches "general temporal reasoning".
- `kind="randomwalk"`: pure geometric Brownian motion with ~zero drift and constant vol — **no
  learnable signal**. The honesty control.

Both feed the SAME `crypto_features.build` -> `X_syn (N,T,10)`, `fwd_syn (N,T)`.

## 5. Pretrain -> fine-tune (`train_eval.py`)

```python
def pretrain_model(make, cfg, X_syn, fwd_syn, epochs=300):
    """Train one model on the WHOLE synthetic panel (no val split needed; this is a prior, not a
    selected model). Returns its state_dict (CPU tensors)."""
    # seed, standardize X_syn with its own mu/sd, build model+opt+warmup sched, run _run_epochs
    # on the full panel, return {k: v.clone() for k,v in net.state_dict().items()}

def make_pretrained_trainer(state):
    """Return a trainer(make, X, fwd, lo, hi, cfg, epochs) that builds the model, loads `state`,
    RESETS net.gate to 0, then fine-tunes on the real [warm,train_hi) window exactly like
    _train_fold (standardize on real train, warmup, best-val capture)."""
```

The driver pretrains ONCE per condition (structured / random-walk), then passes the resulting
`make_pretrained_trainer(state)` as `trainer=` to `nested_walkforward` on the REAL data. Leak-free:
synthetic is parametric (independent of real), and each fold still fine-tunes only on its own past.

Note on scales: the 10 features are already vol-normalized + clipped in `build_features`, so
synthetic and real features share a comparable scale; the fine-tune re-standardizes on the real
train window and continues training, adapting the warm-started weights.

## 6. Evaluation, ablation, success criterion

Real combined-18, leak-free nested WF, `net_returns(..., spread_bps=10)`,
`ann_ir/newey_west_t/deflated_sharpe/durability_by_year`, **PPY=252**, band in {0.0, 0.3}, DSR
`n_trials=len(GATED_GRID)`. Driver `run_dmn_pretrain.py` prints the table and saves
`figures/fig_dmn_pretrain.png` (net IR bars, dashed line at LSTM 0.92):

| model | band | net IR | NW-t | DSR | +2022 |
|-------|------|--------|------|-----|-------|
| LSTM-DMN | none/hard | ~0.92 | ... | ... | ... |
| gated (no pretrain) | none/hard | ~0.29 | ... | ... | ... |
| **gated + structured-pretrain** | none/hard | ... | ... | ... | ... |
| **gated + randomwalk-pretrain** | none/hard | ... | ... | ... | ... |

- **Success (genuine):** `gated+structured` (better band) **net IR > 0.92 AND NW-t > 1.5 AND DSR > 0.8**
  **AND** `structured > randomwalk` by a clear margin -> attention adds genuine value once
  data-starvation is removed.
- **Suspicious:** `structured ~= randomwalk` and both up -> the gain is generic regularization /
  optimization warm-up, not a learned edge; report as such (not a real attention win).
- **Honest null:** neither beats 0.92 -> definitive: attention does not help on this problem even
  with unlimited diversified pretraining; the LSTM/rule remain best. No tuning to force a win.

## 7. Testing (offline, no network)

- `test_synth_data.py`:
  - `make_synthetic("structured")` shape `(T, 18)`; all finite; values > 0.
  - **independence**: average |pairwise correlation| of returns is small (< ~0.15) and ENB is high
    (> ~12 of 18) — the "uncorrelated" requirement (reuse `diversification_check.basket_stats`).
  - **determinism**: same `seed` -> identical panel; different `kind` -> different panels.
- `test_train_eval.py` (extend):
  - `pretrain_model` returns a dict loadable into a fresh `make_gated_hybrid` model.
  - `make_pretrained_trainer(state)` returns a trainer that, on a tiny synthetic real-tensor,
    produces a net with `gate == 0` right after load (before training moves it) and returns a finite
    `best_val_loss` and correct output shape.
- Heavy real training/pretraining only in the driver.

## 8. Conventions

- Synthetic is parametric/seeded (no network, no real-data leakage). Real data from cached
  `combined_close.npz`. No `Co-Authored-By`. Opus for any dispatched subagent. Code/figures English,
  commentary Greek. Figures `git add -f`. `torch.manual_seed(0)` for training determinism;
  `np.random.default_rng(seed)` for the generator. `paper4/` untouched.
