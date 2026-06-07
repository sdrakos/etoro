# paper5 Gated / Frozen Hybrid Attention — Design

**Date:** 2026-06-07
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 3 (evolve), iteration 3 on the crypto+ETF DMN build.

## 1. Goal & scope

The naive hybrid (LSTM encoder + attention, all trained jointly) was **worse** than the LSTM alone
(net IR **-0.57** vs **0.92**): the attention block replaced the LSTM's good representation with an
overfit one before the head. This iteration makes attention **additive and safe** so it can only
help, never destroy the 0.92 signal:

- **A — gated residual attention:** `h = h_lstm + g * attention(h_lstm)` with `g` a single learnable
  **scalar initialized to 0**. At init the model **is** the LSTM (~0.92); training raises `g` only if
  attention helps on validation. Floor ~0.92, upside only.
- **B — two-stage frozen training:** the same gated model, trained in two phases — first the
  LSTM+head (attention off), then **freeze the LSTM** and train only attention+gate+head on the
  fixed LSTM features. Maximally conservative control.

> Question: can attention, made safe, finally add value over the LSTM (0.92)?

**In scope:** a new `GatedHybridMomentumNetwork`; a two-stage trainer; a driver running the full
ablation (fixed-rule / LSTM / naive-hybrid / gated-A / frozen-B) on the combined 18-asset basket,
both bands; offline tests; a figure.

**Out of scope (future):** transfer/pretraining (the data cure), recency-bias/ALiBi, RL, the eToro
engine, the paper.

## 2. Architecture

Approach A (compose, reuse): extend the existing paper5 modules; `paper4/` untouched.

```
paper5/code/
  models.py        # + GatedHybridMomentumNetwork, + make_gated_hybrid, + GATED_GRID
  train_eval.py    # + _train_fold_two_stage; nested_walkforward gains optional `trainer=` param
  run_dmn_gated.py # driver: fixed / LSTM / naive-hybrid / gated / frozen on combined 18, both bands
  tests/           # extend test_models.py, test_train_eval.py
```

The existing `HybridMomentumNetwork` (naive, -0.57) is kept unchanged as the contrast row. The
existing `_train_fold` and `nested_walkforward` default path stay byte-for-byte unchanged so the
LSTM 0.92 and naive-hybrid -0.57 reproduce. Reuse `_block_local_encode`, `_PositionalEncoding`,
`crypto_features`, `band_eval`, `combined_data`, `costs`, `metrics`, `dmn.sharpe_loss`.

## 3. A — GatedHybridMomentumNetwork (`models.py`)

Same I/O as the other models (`x (N,T,10) -> (N,T)` in `[-1,1]`), same `dmn.sharpe_loss`, same
nested walk-forward.

```python
class GatedHybridMomentumNetwork(nn.Module):
    def __init__(self, n_features, hidden=16, nheads=2, dropout=0.1, window=256):
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.pos  = _PositionalEncoding(hidden)
        self.enc  = TransformerEncoder(TransformerEncoderLayer(hidden, nheads, 4*hidden,
                                       dropout, batch_first=True, norm_first=True), 1)
        self.gate = nn.Parameter(torch.zeros(1))     # scalar, init 0  -> attention starts invisible
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        h, _ = self.lstm(x)
        a = _block_local_encode(self.enc, self.pos, h, self.window)
        h = h + self.gate * a                         # gated residual
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)
```

- **Scalar gate `g` init 0** (the user's choice: max safety, the gate itself cannot overfit). At
  init `h = h_lstm` exactly, so the model is an LSTM->head (the 0.92 architecture) with attention
  contributing nothing.
- `make_gated_hybrid(n_features, cfg)`; `GATED_GRID` cfg dicts:
  `{"hidden":16,"nheads":2,"dropout":0.1,"wd":1e-3,"warmup":50}`,
  `{"hidden":16,"nheads":2,"dropout":0.3,"wd":1e-2,"warmup":50}`,
  `{"hidden":8,"nheads":2,"dropout":0.3,"wd":1e-2,"warmup":50}`. (`nheads` divides `hidden`.)
- **Leak-free**: LSTM causal + block-local-causal attention -> the causal test must pass.

## 4. B — Two-stage frozen trainer (`train_eval.py`)

A new `_train_fold_two_stage(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2)` on the **same**
`GatedHybridMomentumNetwork`:

1. **Stage 1** — freeze `enc` + `gate` (`requires_grad=False`); train `lstm` + `head` for
   `epochs//2` epochs (warmup applies). The model behaves as a pure LSTM (gate=0, attention frozen)
   and reaches ~0.92.
2. **Stage 2** — freeze `lstm` (`requires_grad=False`); unfreeze `enc` + `gate` + `head`; train for
   the remaining `epochs - epochs//2` epochs. Attention learns on **fixed** LSTM features.
3. Validation-select / early-stop exactly as `_train_fold` does (best validation loss across the run;
   the existing val split logic). Return `(net, mu, sd, best_val_loss)`.

To avoid duplicating the optimization code, factor the per-epoch inner step of `_train_fold`
(forward, sharpe_loss backward, grad-clip, opt.step, sched.step, periodic validation capture) into a
shared helper `_run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs)` used by both `_train_fold` and
each stage of `_train_fold_two_stage`. `_train_fold`'s observable behavior must be unchanged
(refactor guarded by the existing nested-WF test).

`nested_walkforward` gains an optional `trainer=_train_fold` parameter; it calls
`trainer(make, X, fwd, warm, train_hi, cfg, epochs)` per fold. Default keeps the current behavior;
the B run passes `trainer=_train_fold_two_stage`.

## 5. Evaluation, ablation, success criterion

Identical harness: leak-free nested WF, `costs.net_returns(..., spread_bps=10)`,
`ann_ir/newey_west_t/deflated_sharpe/durability_by_year`, **PPY=252**, combined 18-asset basket,
band in {0.0, 0.3}, DSR `n_trials=len(grid)`. Driver `run_dmn_gated.py` prints the table and saves
`figures/fig_dmn_gated.png` (net IR bars, dashed line at the LSTM 0.92):

| model | band | net IR | NW-t | DSR | +2022 |
|-------|------|--------|------|-----|-------|
| fixed-rule | hard | ~1.11 | ... | ... | ... |
| LSTM-DMN | none/hard | ~0.92 | ... | ... | ... |
| naive-hybrid | none/hard | ~-0.57 | ... | ... | ... |
| **gated (A)** | none/hard | ... | ... | ... | ... |
| **frozen (B)** | none/hard | ... | ... | ... | ... |

- **Success:** gated (A) or frozen (B), better band, **net IR > 0.92 AND NW-t > 1.5 AND DSR > 0.8**
  -> attention finally adds value. If they land ~0.92 -> honest "attention does not add but no longer
  hurts". If a gated/frozen run lands materially **below** 0.92 -> a bug (by construction the floor is
  the LSTM); investigate, do not ship. No tuning to force a win.

## 6. Testing (offline, no network)

- `test_models.py`:
  - `make_gated_hybrid` output `(N,T)` in `[-1,1]`.
  - **gate init is 0**: `float(net.gate) == 0.0` on a fresh model.
  - **gate isolation**: with `gate` forced to 0, perturbing the attention encoder's weights does NOT
    change the output (proves the residual gate truly isolates attention at g=0).
  - **gated causal check**: perturbing the last timestep leaves earlier outputs unchanged.
- `test_train_eval.py`:
  - `_train_fold_two_stage` on a tiny synthetic tensor returns a finite `best_val_loss` and a net
    whose forward gives the right shape.
  - **stage freezing**: a small unit check that after stage 1 setup the `enc`/`gate` params have
    `requires_grad=False` while `lstm` is trainable, and the inverse after stage 2 setup. (Test the
    freeze helper directly, not a full train.)
  - existing `_train_fold` / warmup / nested-WF tests still pass (refactor guard).
- Heavy real training only in the driver.

## 7. Conventions

- Train on Yahoo (cached `combined_close.npz`); serving is a later spec.
- No `Co-Authored-By`. Opus for any dispatched subagent. Code/figures English, commentary Greek.
  Figures `git add -f`. Determinism `torch.manual_seed(0)`. `paper4/` untouched.
