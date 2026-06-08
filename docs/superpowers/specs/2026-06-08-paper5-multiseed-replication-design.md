# paper5 Multi-Seed Replication + Attention-Attribution — Design

**Date:** 2026-06-08
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 4 (honest validation) on the crypto+ETF DMN build.

## 1. Goal & scope

The synthetic-pretraining run produced one striking number on a single seed: random-walk (signalless)
pretrain -> fine-tune gave net IR **1.28** (best of the whole arc), while structured-pretrain
collapsed (-0.04). Two open questions remain, both answerable by one experiment:

1. **Is 1.28 robust or a lucky seed?** A single (init + synthetic) draw can be noise.
2. **Does attention contribute at all, or is the lift pure LSTM initialization?** We never logged the
   final gate; the 1.28 may be a better-initialized LSTM with attention effectively off.

Run a **2x2 + structured factorial across 5 seeds** on the real combined-18 basket and report
distributions (mean +/- std) plus the gate magnitude.

**In scope:** module-level seed control in `train_eval.py` (so each run varies the synthetic data and
the weight init); a `GATE_LOG` diagnostic; a replication driver that loops 6 conditions x 5 seeds,
evaluates on real OOS (hard band), and prints a mean+/-std table + a figure; offline tests.

**Out of scope (future):** ^VIX feature, hourly data, the eToro engine, the paper.

## 2. Experiment design (locked)

- **Conditions (6):** `{LSTM, gated} x {no-pretrain, rwalk-pretrain, structured-pretrain}`.
  - LSTM = `make_lstm` with `LSTM_GRID[0]` (single cfg, for a fair 1-trial comparison with gated).
  - gated = `make_gated_hybrid` with `GATED_GRID[0]`.
  - rwalk/structured pretrain = `pretrain_model` on `synth_data.make_synthetic(kind, 18, 6000, seed)`,
    then `make_pretrained_trainer(state)` (warm-start, gate reset 0). no-pretrain = default `_train_fold`.
- **Seeds:** 0,1,2,3,4. Each seed varies BOTH the synthetic dataset (`make_synthetic(seed=s)`) and the
  weight init / training RNG (`train_eval.set_seed(s)`).
- **Evaluation:** real combined-18, leak-free nested WF, `net_returns(spread_bps=10)`, `ann_ir`,
  `newey_west_t`, `deflated_sharpe`, PPY=252, **hard band (0.3)** as the single reported metric
  (the production config; avoids doubling the table with the noisier no-band column).
- **Pre-registered interpretation** (decided BEFORE seeing results):
  1. **1.28 robust?** `gated+rwalk` mean clearly > 0.92 with modest std (1.28 inside the distribution)
     -> robust. mean ~= 0.92 or huge std -> 1.28 was luck.
  2. **Attention irrelevant?** `LSTM+rwalk` ~= `gated+rwalk` (overlapping distributions) AND
     `mean|gate| ~= 0` -> the gain is pure LSTM initialization; the transformer adds nothing.
     `gated+rwalk` clearly > `LSTM+rwalk` -> attention genuinely adds value (first time).
  3. **Structured** (both models) should collapse consistently (confirmation of the bake-in trap).
  No tuning to force any outcome; whatever the distributions say is the result.

## 3. Architecture

Extend existing paper5 modules (paper4 untouched).

```
paper5/code/
  train_eval.py          # + _SEED module global + set_seed(s); torch.manual_seed(0) -> torch.manual_seed(_SEED)
                         # + GATE_LOG list + gated trainers append final |gate|
  run_dmn_replicate.py   # driver: 6 conditions x 5 seeds on real combined-18; mean+/-std table + figure
  tests/                 # extend test_train_eval.py (seed control + GATE_LOG)
```

Reuse: `synth_data.make_synthetic`, `pretrain_model`, `make_pretrained_trainer`, `nested_walkforward`
(`trainer=` hook), `evaluate`, `combined_data`, `crypto_features`, `models`, `metrics`, `costs`.

## 4. Seed control + gate logging (`train_eval.py`)

- Add a module global `_SEED = 0` and `def set_seed(s): global _SEED; _SEED = int(s)`.
- Replace the hardcoded `torch.manual_seed(0)` at the top of `_train_fold`, `_train_fold_two_stage`,
  `pretrain_model`, and the closure in `make_pretrained_trainer` with `torch.manual_seed(_SEED)`.
  **At the default `_SEED == 0` this is byte-for-byte identical** to current behavior, so the whole
  existing suite and all prior results reproduce.
- Add `GATE_LOG = []` (module global). In `make_pretrained_trainer`'s closure AND in `_train_fold`,
  after fine-tuning, if the trained `net` has a `gate` attribute, append `abs(float(net.gate))` to
  `GATE_LOG`. (LSTM models have no `.gate` -> nothing appended.) This is a diagnostic side-channel;
  the driver clears it (`GATE_LOG.clear()`) before each gated condition and averages it after.

## 5. Driver (`run_dmn_replicate.py`)

```
for each condition in the 6:
    irs, gates = [], []
    for seed in 0..4:
        train_eval.set_seed(seed)
        if pretrain needed:
            close_syn = synth_data.make_synthetic(kind, 18, 6000, seed=seed)
            X_syn, fwd_syn, _ = crypto_features.build(close_syn)
            state = pretrain_model(make, GRID0, X_syn, fwd_syn, epochs=300)
            trainer = make_pretrained_trainer(state)
        else:
            trainer = None
        train_eval.GATE_LOG.clear()
        POS, _, test_idx = nested_walkforward(make, [GRID0], X_real, fwd_real, folds,
                                              warm=252, epochs=300, trainer=trainer)
        r = evaluate(POS, fwd_real, dates_ms, test_idx, band=0.3, spread_bps=10, n_trials=1, ppy=252)
        irs.append(r["net_ir"])
        if has_gate: gates.append(mean(train_eval.GATE_LOG))
    record mean/std(irs), mean(gates)
```

Print a 6-row table (`condition | netIR mean+/-std | mean|gate|`) and the per-seed values; save
`figures/fig_dmn_replicate.png` (per-condition scatter of the 5 seed points + the mean, with a
dashed line at 0.92). Also print the LSTM-vs-gated comparison for the rwalk column (the attention
verdict). The real data and `folds` are computed once up front.

## 6. Testing (offline, no network, no heavy training)

- `test_train_eval.py` (extend):
  - **seed bites:** `set_seed(1)` then a fresh `make_gated_hybrid` built right after
    `torch.manual_seed(train_eval._SEED)` differs from the same under `set_seed(2)` (the seed changes
    initial weights). Reset `set_seed(0)` at the end.
  - **default unchanged:** with `set_seed(0)`, `_train_fold` on a tiny synthetic tensor returns a
    finite loss and correct output shape (smoke that the `_SEED` swap didn't break the path).
  - **GATE_LOG:** starts empty/clears; after `make_pretrained_trainer(state)` fine-tunes a gated model
    on a tiny tensor, `GATE_LOG` has exactly one non-negative float.
- Heavy multi-seed training only in the driver.

## 7. Conventions

- Synthetic parametric/seeded (no leak); real data from cached `combined_close.npz`. No
  `Co-Authored-By`. Opus for any dispatched subagent. Code/figures English, commentary Greek. Figures
  `git add -f`. `paper4/` untouched. `set_seed` default stays 0 so all prior results reproduce.
