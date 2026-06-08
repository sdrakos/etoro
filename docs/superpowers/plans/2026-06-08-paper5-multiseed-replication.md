# Multi-Seed Replication + Attention-Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether the random-walk-pretrain net IR 1.28 is robust (vs a lucky seed) and whether attention contributes at all, by running a 2x2+structured factorial across 5 seeds on the real combined-18 basket with gate logging.

**Architecture:** Add module-level seed control and a `GATE_LOG` diagnostic to `train_eval.py` (default seed 0 keeps everything byte-identical), guard the gate reset so LSTM models can also be pretrained, and add a driver that loops 6 conditions x 5 seeds and reports mean+/-std net IR plus mean |gate|.

**Tech Stack:** Python 3.11+, PyTorch, NumPy/pandas, matplotlib. Tests: pytest, fully offline.

---

## Context for the implementer (read once)

cwd `etoro/`. Work in `paper5/code/` (bare-import: NO `__init__.py`; tests in `paper5/code/tests/`, run `python -m pytest` from `paper5/code/`). Prior iterations committed; offline suite passes (37 tests). Do NOT modify `paper4/`. Commits: clean `git commit -m "..."`, NO `Co-Authored-By`. Figures: `git add -f`.

**`train_eval.py` currently has** (relevant parts): constants `PPY=365`, `TRAIN_COST=1e-3`, `BASE_LR=1e-3`; `warmup_lambda`; `_prep_tensors`; `_run_epochs`; `_train_fold` (starts with `torch.manual_seed(0)`); `_train_fold_two_stage` (starts with `torch.manual_seed(0)`); `pretrain_model` (starts with `torch.manual_seed(0)`); `make_pretrained_trainer(state)` whose inner `_trainer` starts with `torch.manual_seed(0)` and unconditionally does `with torch.no_grad(): net.gate.zero_()`; `nested_walkforward(make, grid, X, fwd, fold_bounds, warm=252, epochs=300, trainer=None)`; `evaluate(..., ppy=PPY)`.

**`models.py` has** `make_lstm`/`LSTM_GRID`, `make_gated_hybrid`/`GATED_GRID` (GatedHybridMomentumNetwork has a scalar `.gate` Parameter; LSTM models do NOT have `.gate`). `synth_data.make_synthetic(kind, n_assets, T, seed)` and `combined_data.fetch_combined_daily()` exist.

**Key fix in this plan:** `make_pretrained_trainer` must guard `net.gate.zero_()` with `hasattr(net, "gate")`, because the new LSTM+pretrain conditions warm-start an LSTM (no gate).

---

## File Structure

- `paper5/code/train_eval.py` — **modify**: add `_SEED` + `set_seed`, `GATE_LOG`; swap hardcoded seeds to `_SEED`; guard the gate reset; append `|gate|` to `GATE_LOG` after fine-tuning a gated model.
- `paper5/code/run_dmn_replicate.py` — **create**: 6-condition x 5-seed harness on real combined-18.
- `paper5/code/tests/test_train_eval.py` — **modify**: seed-bites, default-unchanged, GATE_LOG tests.

---

## Task R1: Seed control + GATE_LOG + guarded gate reset

**Files:**
- Modify: `paper5/code/train_eval.py`
- Test: `paper5/code/tests/test_train_eval.py`

- [ ] **Step 1: Write the failing tests**

Add to `paper5/code/tests/test_train_eval.py` (imports `train_eval`, `models`, `numpy as np` present):

```python
def test_set_seed_changes_init():
    import torch
    train_eval.set_seed(1)
    torch.manual_seed(train_eval._SEED)
    a = next(models.make_gated_hybrid(10, models.GATED_GRID[0]).parameters()).detach().clone()
    train_eval.set_seed(2)
    torch.manual_seed(train_eval._SEED)
    b = next(models.make_gated_hybrid(10, models.GATED_GRID[0]).parameters()).detach().clone()
    train_eval.set_seed(0)
    assert not torch.allclose(a, b)


def test_set_seed_zero_default_path_runs():
    train_eval.set_seed(0)
    rng = np.random.default_rng(0)
    N, T, F = 3, 120, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    net, mu, sd, best = train_eval._train_fold(models.make_lstm, X, fwd, 0, T, models.LSTM_GRID[0], epochs=4)
    assert np.isfinite(best)


def test_gate_log_records_one_float_for_gated_pretrain():
    train_eval.GATE_LOG.clear()
    rng = np.random.default_rng(0)
    N, T, F = 3, 80, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    trainer = train_eval.make_pretrained_trainer(state)
    trainer(models.make_gated_hybrid, Xs, fs, 0, T, models.GATED_GRID[0], epochs=4)
    assert len(train_eval.GATE_LOG) == 1
    assert train_eval.GATE_LOG[0] >= 0.0


def test_lstm_pretrain_no_gate_reset_error():
    # warm-starting an LSTM (no .gate) must NOT raise in the pretrained trainer.
    rng = np.random.default_rng(0)
    N, T, F = 3, 80, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_lstm, models.LSTM_GRID[0], Xs, fs, epochs=4)
    trainer = train_eval.make_pretrained_trainer(state)
    net, mu, sd, best = trainer(models.make_lstm, Xs, fs, 0, T, models.LSTM_GRID[0], epochs=4)
    assert np.isfinite(best)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -k "seed or gate_log or no_gate_reset" -v`
Expected: FAIL — `test_set_seed_changes_init` errors with `AttributeError: module 'train_eval' has no attribute 'set_seed'`, and `test_lstm_pretrain_no_gate_reset_error` errors on `net.gate` for the LSTM.

- [ ] **Step 3: Implement the changes in `train_eval.py`**

(a) Add module globals right after `BASE_LR = 1e-3`:

```python
_SEED = 0
GATE_LOG = []


def set_seed(s):
    """Set the global training seed (model init + RNG). Default 0 reproduces all prior results."""
    global _SEED
    _SEED = int(s)


def _log_gate(net):
    """Diagnostic: record the absolute final gate of a gated model (no-op for models without one)."""
    g = getattr(net, "gate", None)
    if g is not None:
        GATE_LOG.append(abs(float(g)))
```

(b) In `_train_fold`, `_train_fold_two_stage`, and `pretrain_model`, change the first line `torch.manual_seed(0)` to `torch.manual_seed(_SEED)`.

(c) In `_train_fold`, add `_log_gate(net)` right before `return net, mu, sd, best` (after `net.eval()`).

(d) In `make_pretrained_trainer`'s inner `_trainer`: change `torch.manual_seed(0)` to `torch.manual_seed(_SEED)`; guard the gate reset; and log the gate before returning. The reset block becomes:

```python
        net.load_state_dict(state)
        if hasattr(net, "gate"):
            with torch.no_grad():
                net.gate.zero_()
```

and right before `return net, mu, sd, best` (after `net.eval()`) add `_log_gate(net)`.

- [ ] **Step 4: Run the tests + full suite**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -v`
Expected: PASS (new seed/gate tests + all prior, incl. `test_pretrained_trainer_resets_gate_to_zero` which still holds for the gated model).

Run: `cd paper5/code && python -m pytest tests/ -v`
Expected: PASS (entire offline suite — the `_SEED==0` default keeps everything reproducing).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/train_eval.py paper5/code/tests/test_train_eval.py
git commit -m "feat(paper5): settable training seed + GATE_LOG diagnostic + guarded gate reset for LSTM pretrain"
```

---

## Task R2: Replication driver

**Files:**
- Create: `paper5/code/run_dmn_replicate.py`

No unit test (heavy multi-seed training). Integration entry point.

- [ ] **Step 1: Write the driver**

```python
# paper5/code/run_dmn_replicate.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-seed replication + attention attribution. Runs the 2x2+structured factorial
{LSTM, gated} x {no-pretrain, rwalk-pretrain, structured-pretrain} across 5 seeds on the REAL
combined-18 basket (hard band, net @10bps, PPY=252), and reports net IR mean+/-std plus mean |gate|.
Answers: (1) is the rwalk 1.28 robust? (2) does attention add anything, or is the lift pure LSTM
initialization (gated+rwalk ~= LSTM+rwalk and |gate|~=0)?"""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import metrics  # noqa: F401  (kept for parity with other drivers / future use)
import combined_data, crypto_features, train_eval, models, synth_data

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
SEEDS = [0, 1, 2, 3, 4]
CONDS = [
    ("LSTM noPT",    models.make_lstm,         models.LSTM_GRID[0],  None),
    ("LSTM rwalk",   models.make_lstm,         models.LSTM_GRID[0],  "randomwalk"),
    ("LSTM struct",  models.make_lstm,         models.LSTM_GRID[0],  "structured"),
    ("gated noPT",   models.make_gated_hybrid, models.GATED_GRID[0], None),
    ("gated rwalk",  models.make_gated_hybrid, models.GATED_GRID[0], "randomwalk"),
    ("gated struct", models.make_gated_hybrid, models.GATED_GRID[0], "structured"),
]


def main():
    close = combined_data.fetch_combined_daily()
    X, fwd, dates_ms = crypto_features.build(close)
    T = X.shape[1]
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {close.shape[1]} real assets, {T} bars; folds={len(folds)}; seeds={SEEDS}")

    rows = []           # (name, ir_list, gate_list)
    for name, mk, cfg, kind in CONDS:
        irs, gates = [], []
        for s in SEEDS:
            train_eval.set_seed(s)
            if kind is None:
                trainer = None
            else:
                Xsyn, fsyn, _ = crypto_features.build(synth_data.make_synthetic(kind, 18, 6000, seed=s))
                state = train_eval.pretrain_model(mk, cfg, Xsyn, fsyn, epochs=300)
                trainer = train_eval.make_pretrained_trainer(state)
            train_eval.GATE_LOG.clear()
            POS, _, test_idx = train_eval.nested_walkforward(
                mk, [cfg], X, fwd, folds, warm=252, epochs=300, trainer=trainer)
            r = train_eval.evaluate(POS, fwd, dates_ms, test_idx, 0.3,
                                    spread_bps=10.0, n_trials=1, ppy=PPY)
            irs.append(r["net_ir"])
            g = float(np.mean(train_eval.GATE_LOG)) if train_eval.GATE_LOG else None
            if g is not None:
                gates.append(g)
            print(f"  {name:<13} seed{s}: IR {r['net_ir']:+.2f}" + (f"  |g| {g:.3f}" if g is not None else ""))
        rows.append((name, irs, gates))

    print(f"\n{'condition':<14}{'netIR mean':>12}{'std':>8}{'mean|gate|':>12}")
    print("-" * 46)
    for name, irs, gates in rows:
        gm = f"{np.mean(gates):.3f}" if gates else "-"
        print(f"{name:<14}{np.mean(irs):>12.2f}{np.std(irs):>8.2f}{gm:>12}")

    # attention verdict (rwalk column)
    def col(n):
        return next(irs for nm, irs, _ in rows if nm == n)
    lstm_rw, gated_rw = col("LSTM rwalk"), col("gated rwalk")
    print(f"\n[attention] gated+rwalk {np.mean(gated_rw):.2f}+/-{np.std(gated_rw):.2f}  vs  "
          f"LSTM+rwalk {np.mean(lstm_rw):.2f}+/-{np.std(lstm_rw):.2f}  "
          f"-> diff {np.mean(gated_rw) - np.mean(lstm_rw):+.2f}")

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, (name, irs, _g) in enumerate(rows):
        ax.scatter([i] * len(irs), irs, s=28, color="#64748b", zorder=3)
        ax.scatter([i], [np.mean(irs)], s=120, marker="_", color="#dc2626", zorder=4)
    ax.axhline(0.92, ls="--", color="#2563eb", lw=1, label="LSTM ref 0.92")
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows], rotation=30, ha="right")
    ax.set_ylabel("net IR @10bps (hard band)")
    ax.set_title("Multi-seed replication (5 seeds): pretraining + attention attribution")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_replicate.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_replicate.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the driver end-to-end (long — runs in the background)**

Run: `cd paper5/code && python -u run_dmn_replicate.py`
Expected: per-seed lines, then a 6-row mean+/-std table, an `[attention]` verdict line, and
`[fig] figures/fig_dmn_replicate.png`. This is heavy (30 nested-WF runs + 20 pretrains) — expect a long
runtime; run it in the background and wait for completion.

- [ ] **Step 3: Sanity-check against the pre-registered interpretation**

Record from the table:
- **1.28 robust?** `gated rwalk` mean clearly > 0.92 with modest std (1.28 within the spread) -> robust; mean ~= 0.92 or large std -> 1.28 was luck.
- **Attention irrelevant?** `gated rwalk` ~= `LSTM rwalk` (the `[attention]` diff ~ 0) AND `mean|gate|` ~ 0 -> the lift is pure LSTM initialization; attention adds nothing. A clear positive diff -> attention genuinely helps.
- **Structured** rows (both) should be low/negative (consistent collapse).
Do not tune to force any outcome.

- [ ] **Step 4: Commit (driver + figure)**

```bash
git add paper5/code/run_dmn_replicate.py
git add -f paper5/figures/fig_dmn_replicate.png
git commit -m "feat(paper5): multi-seed replication driver (2x2+structured, gate attribution)"
```

---

## Task R3: Record the verdict (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (paper5 Phase-3 findings — targeted Edit; a parallel session also edits this file)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the replication outcome to the paper5 findings in `etoro/CLAUDE.md`**

Add one bullet with the measured `gated rwalk` and `LSTM rwalk` mean+/-std, the `mean|gate|`, and the verdict on the two questions (1.28 robust? attention relevant?). Fill from Task R2's table; do not invent. Use a targeted Edit anchored on existing text.

- [ ] **Step 2: Update the memory file** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line: the replication mean+/-std, gate magnitude, and the attention verdict. Keep it one fact. (Memory files are outside the repo — save with the Write tool.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record multi-seed replication + attention-attribution verdict"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 3 modules (train_eval seed/GATE_LOG + run_dmn_replicate + tests) -> Tasks R1-R3. ✓
- Spec section 2 design (6 conditions = 2x2+structured, 5 seeds, hard-band eval on real, pre-registered interpretation) -> Task R2 driver (`CONDS`, `SEEDS`, band=0.3) + Step 3. ✓
- Spec section 4 (`_SEED`+`set_seed`; swap the four hardcoded seeds; default-0 identical; `GATE_LOG` + append from gated trainers) -> Task R1 (a)-(d). ✓
- Spec implicit requirement (LSTM+pretrain must not crash on the gate reset) -> Task R1 (d) guards `net.gate.zero_()` with `hasattr`; `test_lstm_pretrain_no_gate_reset_error` covers it. ✓
- Spec section 5 driver loop (set_seed -> optional pretrain -> clear GATE_LOG -> nested_walkforward -> evaluate hard band -> collect; table + figure + attention line) -> Task R2 verbatim. ✓
- Spec section 6 testing (seed bites, default unchanged, GATE_LOG one float) -> Task R1 tests (plus the LSTM-no-crash test). ✓
- Spec section 7 conventions -> Context + commit steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". `<...>` verdict numbers in R3 are experiment outputs unavailable before R2 runs; instructions say fill from the table, don't invent. Acceptable.

**3. Type consistency:** `set_seed(s)` sets `train_eval._SEED`, read by `torch.manual_seed(_SEED)` in all four train funcs. `_log_gate(net)` appends to `GATE_LOG`; called in `_train_fold` and the pretrained `_trainer`; LSTM models have no `.gate` so nothing is appended. Driver: `mk` (model factory) + `cfg` (single dict) + `kind` (None/"randomwalk"/"structured"); `pretrain_model(mk, cfg, Xsyn, fsyn, epochs)` -> state -> `make_pretrained_trainer(state)` -> trainer passed to `nested_walkforward(mk, [cfg], ..., trainer=trainer)`; `evaluate(..., band=0.3, n_trials=1, ppy=252)` returns `net_ir`. `make_synthetic(kind, 18, 6000, seed=s)` -> `crypto_features.build` -> `(X,fwd,_)`. All consistent with committed signatures. ✓
```
