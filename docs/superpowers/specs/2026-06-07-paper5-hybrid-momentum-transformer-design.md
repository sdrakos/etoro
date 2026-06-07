# paper5 Hybrid Momentum Transformer (LSTM+attention) — Design

**Date:** 2026-06-07
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 3 (evolve), iteration 2 on the crypto+ETF DMN build.

## 1. Goal & scope

The first DMN build found the pure Momentum Transformer **data-starved** (net IR ~0.07 even on the
diversified 18-asset basket where the LSTM DMN reached 0.92). Diagnosis: a pure attention model has
too many degrees of freedom for ~3000 daily bars. This iteration builds the **real** Momentum
Transformer of Wood (2022) — an **LSTM encoder followed by attention** — so it inherits the LSTM's
sample efficiency and adds attention's regime adaptation, plus the two training fixes transformers
need on small data (**pre-LN** and **LR warmup**).

> Question: does attention **on top of the LSTM** add value over the LSTM alone (0.92)?

**In scope:** a new `HybridMomentumNetwork` (LSTM → pre-LN block-local causal attention → tanh head);
LR warmup in the training loop (per-cfg, LSTM unchanged); a driver that runs the full ablation
(fixed-rule / LSTM-DMN / pure-Transformer / hybrid) on the combined 18-asset basket at both bands;
offline tests; a figure.

**Out of scope (future):** recency-bias/ALiBi, transfer/pretraining (hourly or synthetic),
data augmentation, ensembling, the eToro engine, the paper.

## 2. Architecture

Approach A — **compose existing pieces**. Reuse `paper4/code` as a library (never modified) and the
existing paper5 modules. The hybrid is a new class in `models.py`; warmup is a small addition to
`train_eval._train_fold`; a new driver mirrors `run_dmn_combined.py`.

```
paper5/code/
  models.py            # + HybridMomentumNetwork, + make_hybrid, + HYBRID_GRID; pure-Tr gets norm_first option
  train_eval.py        # + linear LR warmup in _train_fold (per-cfg, default off)
  run_dmn_hybrid.py    # driver: fixed-rule / LSTM / pure-Tr / hybrid on combined 18, both bands
  tests/               # extend test_models.py, test_train_eval.py
```

Unchanged reuse: `crypto_features`, `band_eval`, `combined_data`, `costs`, `metrics`,
`dmn.sharpe_loss`, the nested-WF/evaluate in `train_eval`.

## 3. The HybridMomentumNetwork (`models.py`)

Same I/O as the other models: `x (N,T,10) -> positions (N,T)` in `[-1,1]`, trained with the same
`dmn.sharpe_loss` under the same nested walk-forward (fair comparison).

```
x (N,T,10)
  -> nn.LSTM(10 -> hidden)                         # (N,T,hidden) hidden-state sequence (long memory)
  -> block-local causal attention (pre-LN)         # window=256, norm_first=True, over the hidden states
  -> Dropout -> tanh(Linear(hidden -> 1))          # (N,T) position
```

- The attention is the **same block-local causal mechanism** already in `MomentumTransformer`
  (O(T*window), leak-free), but it operates on the LSTM hidden states instead of raw features. To
  avoid duplicating the block-local forward logic, factor it into a reusable
  `_block_local_encode(enc, pos, x, window)` helper used by both `MomentumTransformer` and
  `HybridMomentumNetwork`.
- `d_model = hidden` (attention runs in the LSTM's hidden dimension; no extra projection needed; a
  single `nn.Linear(10->hidden)` is the LSTM itself).
- **pre-LN**: build the `nn.TransformerEncoderLayer` with `norm_first=True`. The existing
  `MomentumTransformer` gains the same `norm_first` constructor arg (default keeps current behavior
  so its committed 0.07 result is reproducible as the reference row).
- `make_hybrid(n_features, cfg)` with `HYBRID_GRID` of cfg dicts:
  `{"hidden":16,"nheads":2,"dropout":0.1,"wd":1e-3,"warmup":50}`,
  `{"hidden":16,"nheads":2,"dropout":0.3,"wd":1e-2,"warmup":50}`,
  `{"hidden":8,"nheads":2,"dropout":0.3,"wd":1e-2,"warmup":50}`.
  (`d_model` is taken as `hidden`; `nheads` must divide `hidden`.)
- **Leak-free**: the LSTM is causal; the attention is block-local causal — the existing causal test
  (perturb a future timestep, earlier outputs unchanged) must pass for the hybrid too.

## 4. Warmup + pre-LN in training (`train_eval.py`)

- Add **linear LR warmup** to `_train_fold`: for the first `warmup` optimizer steps, the learning
  rate ramps linearly 0 -> `base_lr` (1e-3), then stays at `base_lr`. Implemented with a
  `torch.optim.lr_scheduler.LambdaLR` whose lambda is `min(1.0, (step+1)/warmup)` (and `1.0`
  identically when `warmup == 0`). Read `warmup = cfg.get("warmup", 0)`.
- **Fairness / reproducibility:** LSTM cfgs carry no `warmup` key -> `warmup=0` -> constant LR ->
  the LSTM training path is **byte-for-byte unchanged**, so its committed 0.92 reproduces. Only
  pure-Transformer and hybrid cfgs set `warmup>0`.
- pre-LN is a **model** choice (constructor `norm_first`), not part of the loop.

## 5. Evaluation, ablation, success criterion

- Identical to the prior build: leak-free nested WF, `costs.net_returns(..., spread_bps=10)`,
  `metrics.ann_ir/newey_west_t/deflated_sharpe/durability_by_year`, **PPY=252**, combined 18-asset
  basket, band in {0.0, 0.3}. DSR `n_trials = len(grid)` per model.
- Driver `run_dmn_hybrid.py` prints the ablation table and saves `figures/fig_dmn_hybrid.png`
  (net IR bars with a dashed line at the LSTM's 0.92):

| model | band | net IR | NW-t | DSR | +2022 |
|-------|------|--------|------|-----|-------|
| fixed-rule | hard | ~1.11 | ... | ... | ... |
| LSTM-DMN | none / hard | ... | ... | ... | ... |
| pure-Transformer | none / hard | ... | ... | ... | ... |
| **hybrid** | none / hard | ... | ... | ... | ... |

- **Success criterion:** the hybrid (better band) reaches **net IR >= 0.92 AND NW-t > 1.5 AND
  DSR > 0.8** -> attention added value over the LSTM. Otherwise -> **honest null** (attention does
  not help in this data regime), reported as-is. No tuning to force a win.

## 6. Testing (offline, no network)

Extend the existing suites (run `pytest` from `paper5/code/`):
- `test_models.py`:
  - `make_hybrid` output is `(N,T)` within `[-1,1]`.
  - **Hybrid causal check**: perturbing the last timestep's input leaves all earlier outputs
    unchanged (LSTM + block-local-causal attention => leak-free).
  - `MomentumTransformer(..., norm_first=True)` constructs and runs (pre-LN path).
- `test_train_eval.py`:
  - The warmup schedule: with `warmup=10`, the LR at step 0 is < `base_lr` and rises to `base_lr`
    by step 10 (assert monotonic non-decreasing over the warmup window, then constant).
  - `warmup=0` yields constant `base_lr` at every step (LSTM path unchanged).
- Heavy real training stays only in the driver.

## 7. Conventions

- Train on Yahoo (cached `combined_close.npz`); serving is a later spec.
- No `Co-Authored-By` in commits. Opus for any dispatched subagent. Code/figures English; commentary
  Greek. Figures committed with `git add -f`. Determinism via `torch.manual_seed(0)` (already in
  `_train_fold`).
- Do NOT modify `paper4/`.
