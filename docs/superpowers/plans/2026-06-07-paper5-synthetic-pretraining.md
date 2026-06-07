# Synthetic-Daily Pretraining for Attention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pretrain the gated hybrid attention on unlimited, uncorrelated, parametric synthetic daily data, then fine-tune on the real combined-18 basket, and honestly test (with a random-walk-pretrain control) whether attention finally beats the LSTM (0.92) once data-starvation is removed.

**Architecture:** Add a parametric synthetic generator (`synth_data.py`) producing N independent series; add `pretrain_model` + `make_pretrained_trainer` to `train_eval.py` (warm-start all weights, reset the scalar gate to 0, fine-tune per fold via the existing `trainer=` hook); a driver runs the four-row ablation on real data, eval-only-on-real and leak-free (synthetic is parametric, independent of the real OOS).

**Tech Stack:** Python 3.11+, PyTorch, NumPy/pandas, matplotlib. Tests: pytest, fully offline (synthetic tensors, no network).

---

## Context for the implementer (read once)

cwd `etoro/`. Work in `paper5/code/` (bare-import: NO `__init__.py`; tests in `paper5/code/tests/`, run `python -m pytest` from `paper5/code/`). Prior iterations committed; offline suite passes (31 tests). Do NOT modify `paper4/`. Commits: clean `git commit -m "..."`, NO `Co-Authored-By`. Figures: `git add -f`.

**`models.py` has:** `GatedHybridMomentumNetwork` (has `.lstm/.enc/.gate/.head`; `gate` is a scalar `nn.Parameter` init 0), `make_gated_hybrid(n_features, cfg)`, `GATED_GRID` (3 cfgs; `GATED_GRID[0] = {"hidden":16,"nheads":2,"dropout":0.1,"wd":1e-3,"warmup":50}`), `make_lstm`, `LSTM_GRID`.

**`train_eval.py` has:** `PPY=365`, `BASE_LR=1e-3`, `TRAIN_COST=1e-3`, `warmup_lambda(step, warmup)`, `make_folds`, `_prep_tensors(X, fwd, lo, hi, val_frac) -> (mu, sd, Xtr, ftr, Xv, fv)`, `_run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs, best=inf, best_state=None) -> (best, best_state)` (trains `net` IN PLACE; after it returns `net` holds the FINAL-epoch weights and `best_state` is the best-validation snapshot), `_train_fold`, `_predict`, `nested_walkforward(make, grid, X, fwd, fold_bounds, warm=252, epochs=300, trainer=None)` (defaults `trainer=_train_fold`; calls `trainer(make, X, fwd, warm, train_hi, cfg, epochs)`), `evaluate(POS, fwd, dates_ms, test_idx, band, spread_bps=10.0, n_trials=1, short_fin=0.0, ppy=PPY)`.

**`crypto_features.build(close_df) -> (X (N,T,10), fwd (N,T), dates_ms)`** works on ANY close DataFrame (so it works on synthetic closes too). **`diversification_check.basket_stats(close_df) -> (corr, avg_abs_rho, enb)`** exists (Task from a prior iteration) for the independence test. **`combined_data.fetch_combined_daily()`** returns the real (T,18) panel from cache.

**Key architecture constraint:** `load_state_dict` requires the SAME architecture. So all three gated conditions (no-pretrain / structured / randomwalk) use ONE fixed cfg `GATED_GRID[0]` (grid of size 1), and pretraining uses that same cfg — so the pretrained weights load into the fine-tune model. The LSTM row keeps its normal `LSTM_GRID` (it is just the reference baseline).

**Determinism:** `torch.manual_seed(0)` for training; `numpy.random.default_rng(seed)` for the generator.

---

## File Structure

- `paper5/code/synth_data.py` — **create**: `make_synthetic(kind, n_assets, T, seed)` -> (T,N) DataFrame of independent synthetic closes; `structured` + `randomwalk`.
- `paper5/code/train_eval.py` — **modify**: add `pretrain_model(...)` + `make_pretrained_trainer(state)`.
- `paper5/code/run_dmn_pretrain.py` — **create**: 4-row ablation driver on real combined-18.
- `paper5/code/tests/test_synth_data.py` — **create**: shape / independence(ENB) / determinism / kind-differs.
- `paper5/code/tests/test_train_eval.py` — **modify**: pretrain loadable + trainer gate-reset + finite.

---

## Task S1: Synthetic generator

**Files:**
- Create: `paper5/code/synth_data.py`
- Create: `paper5/code/tests/test_synth_data.py`

- [ ] **Step 1: Write the failing tests**

```python
# paper5/code/tests/test_synth_data.py
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import synth_data
import diversification_check as dc


def test_shape_and_finite_positive():
    df = synth_data.make_synthetic("structured", n_assets=18, T=1500, seed=0)
    assert df.shape == (1500, 18)
    assert np.isfinite(df.to_numpy()).all()
    assert (df.to_numpy() > 0).all()


def test_series_are_uncorrelated_high_enb():
    df = synth_data.make_synthetic("structured", n_assets=18, T=1500, seed=0)
    _corr, avg, enb = dc.basket_stats(df)
    assert avg < 0.15            # near-zero average pairwise correlation
    assert enb > 12.0            # of 18 -> high effective number of bets (perfect-ish diversity)


def test_determinism_and_kind_differs():
    a = synth_data.make_synthetic("structured", n_assets=4, T=500, seed=1)
    b = synth_data.make_synthetic("structured", n_assets=4, T=500, seed=1)
    assert np.allclose(a.to_numpy(), b.to_numpy())                 # same seed -> identical
    c = synth_data.make_synthetic("randomwalk", n_assets=4, T=500, seed=1)
    assert not np.allclose(a.to_numpy(), c.to_numpy())             # different kind -> different
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_synth_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synth_data'`.

- [ ] **Step 3: Implement the generator**

```python
# paper5/code/synth_data.py
"""Parametric synthetic daily generator for pretraining the attention model. Produces N MUTUALLY
INDEPENDENT (uncorrelated) daily close series so the portfolio-Sharpe loss gets perfect diversity
(ENB ~ N) plus unlimited 'time' -- the two things attention lacked on real data. Parametric (NOT
bootstrapped from real prices) => no leakage of the real OOS. 'structured' = a per-series random mix
of trend / mean-reversion / vol-clustering / jumps; 'randomwalk' = pure GBM, no signal (the honesty
control)."""
from __future__ import annotations
import numpy as np
import pandas as pd

BUSINESS_START = "2000-01-03"


def _series_structured(rng, T):
    """One independent daily return series: regime-switching mix of drift (trend), mean-reversion,
    GARCH-like vol clustering, and occasional jumps. Returns (T,) simple returns."""
    r = np.zeros(T)
    w, a, b = 1e-5, 0.08, 0.90              # GARCH(1,1)-like vol process
    sig2 = w / (1 - a - b)
    level = 0.0                              # running cumulative-return level for mean-reversion
    t = 0
    while t < T:
        seglen = int(rng.integers(20, 120))
        mode = rng.choice(["trend", "mr", "flat"], p=[0.4, 0.4, 0.2])
        drift = float(rng.normal(0, 4e-4)) if mode == "trend" else 0.0
        kappa = float(rng.uniform(0.02, 0.10)) if mode == "mr" else 0.0
        for _ in range(seglen):
            if t >= T:
                break
            if t > 0:
                sig2 = w + a * r[t - 1] ** 2 + b * sig2
            eps = float(rng.normal(0, np.sqrt(sig2)))
            r[t] = drift - kappa * level + eps
            if rng.random() < 0.01:          # rare jump
                r[t] += float(rng.normal(0, 0.05))
            level += r[t]
            t += 1
    return r


def _series_randomwalk(rng, T):
    """Pure GBM returns, ~zero drift, constant vol -> NO learnable signal (honesty control)."""
    return rng.normal(0.0, 0.01, T)


def make_synthetic(kind="structured", n_assets=18, T=6000, seed=0):
    """Return a (T, n_assets) DataFrame of INDEPENDENT synthetic daily closes (each starts at 100).
    kind in {"structured", "randomwalk"}. Deterministic in `seed`."""
    rng = np.random.default_rng(seed)
    gen = _series_structured if kind == "structured" else _series_randomwalk
    cols = {}
    for j in range(n_assets):
        r = gen(rng, T)                      # sequential draws => series are independent
        cols[f"S{j:02d}"] = 100.0 * np.cumprod(1.0 + r)
    idx = pd.bdate_range(BUSINESS_START, periods=T)
    return pd.DataFrame(cols, index=idx)
```

- [ ] **Step 4: Run the tests**

Run: `cd paper5/code && python -m pytest tests/test_synth_data.py -v`
Expected: PASS (3 passed). If `enb` is marginally below 12 at T=1500, that means the series are accidentally correlated — do NOT lower the threshold; check that each series draws fresh from the shared `rng` (sequential draws are independent).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/synth_data.py paper5/code/tests/test_synth_data.py
git commit -m "feat(paper5): parametric synthetic daily generator (independent series; structured + randomwalk)"
```

---

## Task S2: pretrain_model + make_pretrained_trainer

**Files:**
- Modify: `paper5/code/train_eval.py`
- Test: `paper5/code/tests/test_train_eval.py`

- [ ] **Step 1: Write the failing tests**

Add to `paper5/code/tests/test_train_eval.py` (imports `train_eval`, `models`, `numpy as np` already present):

```python
def test_pretrain_model_returns_loadable_state():
    rng = np.random.default_rng(0)
    N, T, F = 4, 120, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    m = models.make_gated_hybrid(F, models.GATED_GRID[0])
    m.load_state_dict(state)                      # must load without error


def test_pretrained_trainer_resets_gate_to_zero():
    import torch
    rng = np.random.default_rng(0)
    N, T, F = 3, 80, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    trainer = train_eval.make_pretrained_trainer(state)
    # epochs=0 -> no fine-tuning -> the gate must be exactly 0 right after warm-start+reset
    net, mu, sd, best = trainer(models.make_gated_hybrid, Xs, fs, 0, T, models.GATED_GRID[0], epochs=0)
    assert float(net.gate) == 0.0


def test_pretrained_trainer_finetunes_finite():
    import torch
    rng = np.random.default_rng(0)
    N, T, F = 3, 120, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    trainer = train_eval.make_pretrained_trainer(state)
    net, mu, sd, best = trainer(models.make_gated_hybrid, Xs, fs, 0, T, models.GATED_GRID[0], epochs=6)
    assert np.isfinite(best)
    with torch.no_grad():
        out = net((torch.tensor(Xs[:, :20], dtype=torch.float32) - mu) / sd)
    assert out.shape == (3, 20)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -k "pretrain" -v`
Expected: FAIL with `AttributeError: module 'train_eval' has no attribute 'pretrain_model'`.

- [ ] **Step 3: Implement**

In `paper5/code/train_eval.py`, add (after `_train_fold_two_stage`):

```python
def pretrain_model(make, cfg, X_syn, fwd_syn, epochs=300):
    """Pretrain one model on the FULL synthetic panel and return its state_dict (CPU clones). This is
    a PRIOR (a warm-start), not a selected model -> no val split; we keep the final-epoch weights.
    X_syn (N,T,F), fwd_syn (N,T)."""
    torch.manual_seed(0)
    Xt = torch.tensor(X_syn, dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True)
    sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (Xt - mu) / sd
    ftr = torch.tensor(fwd_syn, dtype=torch.float32)
    net = make(X_syn.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, cfg.get("warmup", 0)))
    _run_epochs(net, opt, sched, Xtr, ftr, Xtr, ftr, epochs)   # val=train: no selection, keep final
    net.eval()
    return {k: v.detach().clone() for k, v in net.state_dict().items()}


def make_pretrained_trainer(state):
    """Return a trainer(make, X, fwd, lo, hi, cfg, epochs) that warm-starts from `state`, RESETS the
    scalar gate to 0, then fine-tunes on the real [lo,hi) window exactly like _train_fold."""
    def _trainer(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
        torch.manual_seed(0)
        mu, sd, Xtr, ftr, Xv, fv = _prep_tensors(X, fwd, lo, hi, val_frac)
        net = make(X.shape[2], cfg)
        net.load_state_dict(state)
        with torch.no_grad():
            net.gate.zero_()                       # start fine-tuning as an LSTM (gate 0)
        opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, cfg.get("warmup", 0)))
        best, best_state = _run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs)
        if best_state is not None:
            net.load_state_dict(best_state)
        net.eval()
        return net, mu, sd, best
    return _trainer
```

- [ ] **Step 4: Run the tests + full suite**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -v`
Expected: PASS (pretrain tests + all prior).

Run: `cd paper5/code && python -m pytest tests/ -v`
Expected: PASS (entire offline suite).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/train_eval.py paper5/code/tests/test_train_eval.py
git commit -m "feat(paper5): synthetic pretrain_model + warm-start fine-tune trainer (gate reset)"
```

---

## Task S3: Driver — pretraining ablation on real combined 18

**Files:**
- Create: `paper5/code/run_dmn_pretrain.py`

No unit test (needs cached real data + heavy training). Integration entry point.

- [ ] **Step 1: Write the driver**

```python
# paper5/code/run_dmn_pretrain.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iteration 4: does attention beat the LSTM (0.92) if we remove its data-starvation? Pretrain the
gated hybrid on unlimited, uncorrelated, parametric synthetic daily data, then fine-tune on the REAL
combined-18 basket. Honesty control: a random-walk-pretrain (no signal) must NOT produce a win.
All gated conditions use ONE fixed cfg (GATED_GRID[0]) so the pretrained weights load. Eval only on
real OOS, net @10bps, PPY=252. Prints the table and saves fig_dmn_pretrain.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models, synth_data

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
PRE = models.GATED_GRID[0]            # single fixed gated cfg for all gated conditions


def fixed_rule_baseline(close, dates_ms):
    ret = close.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(PPY)
    pos = (np.sign(close.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
    pos = pos.ewm(span=5, min_periods=1).mean()
    from band_eval import apply_band
    W = apply_band(pos.values, 0.3) / close.shape[1]
    fwd = ret.shift(-1).values
    m = np.isfinite(fwd).all(axis=1)
    net = costs.net_returns(W[m], fwd[m], 10.0, 0.0)
    d = np.asarray(dates_ms)[m]
    fin = np.isfinite(net); net, d = net[fin], d[fin]
    return {"net_ir": metrics.ann_ir(net, PPY), "nw_t": metrics.newey_west_t(net),
            "dsr": metrics.deflated_sharpe(net, 1, PPY),
            "durability": metrics.durability_by_year(net, d, PPY), "n": len(net)}


def _row(name, band, r):
    y2022 = r["durability"].get(2022)
    pos2022 = "yes" if (y2022 is not None and y2022 > 0) else ("no" if y2022 is not None else "n/a")
    return (name, band, r["net_ir"], r["nw_t"], r["dsr"], pos2022)


def main():
    close = combined_data.fetch_combined_daily()
    X, fwd, dates_ms = crypto_features.build(close)
    T = X.shape[1]
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {close.shape[1]} real assets, {T} bars; folds={len(folds)}")

    # pretrain on synthetic (parametric -> leak-free); 18 uncorrelated series, 6000 bars
    print("[pretrain] structured ...")
    Xs, fs, _ = crypto_features.build(synth_data.make_synthetic("structured", 18, 6000, seed=0))
    state_struct = train_eval.pretrain_model(models.make_gated_hybrid, PRE, Xs, fs, epochs=300)
    print("[pretrain] randomwalk ...")
    Xr, fr, _ = crypto_features.build(synth_data.make_synthetic("randomwalk", 18, 6000, seed=0))
    state_rw = train_eval.pretrain_model(models.make_gated_hybrid, PRE, Xr, fr, epochs=300)

    rows = [_row("fixed-rule", "hard", fixed_rule_baseline(close, dates_ms))]
    runs = [
        ("LSTM-DMN",     models.make_lstm,         models.LSTM_GRID, None),
        ("gated-noPT",   models.make_gated_hybrid, [PRE],            None),
        ("gated+struct", models.make_gated_hybrid, [PRE],            train_eval.make_pretrained_trainer(state_struct)),
        ("gated+rwalk",  models.make_gated_hybrid, [PRE],            train_eval.make_pretrained_trainer(state_rw)),
    ]
    for name, make, grid, trainer in runs:
        POS, chosen, test_idx = train_eval.nested_walkforward(
            make, grid, X, fwd, folds, warm=252, epochs=300, trainer=trainer)
        for band, tag in [(0.0, "none"), (0.3, "hard")]:
            r = train_eval.evaluate(POS, fwd, dates_ms, test_idx, band,
                                    spread_bps=10.0, n_trials=len(grid), ppy=PPY)
            rows.append(_row(name, tag, r))

    print(f"\n{'model':<14}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'+2022':>8}")
    print("-" * 52)
    for nm, bd, ir, t, dsr, y in rows:
        print(f"{nm:<14}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{y:>8}")

    lstm_best = max(r[2] for r in rows if r[0] == "LSTM-DMN")
    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    palette = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "gated-noPT": "#94a3b8",
               "gated+struct": "#16a34a", "gated+rwalk": "#f59e0b"}
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.bar(labels, irs, color=[palette[r[0]] for r in rows])
    ax.axhline(lstm_best, ls="--", color="#2563eb", lw=1, label=f"LSTM best {lstm_best:.2f}")
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR @10bps")
    ax.set_title("Synthetic-pretrain attention vs LSTM (real combined 18, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_pretrain.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_pretrain.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the driver end-to-end**

Run: `cd paper5/code && python -u run_dmn_pretrain.py`
Expected: two `[pretrain]` lines, then a 9-row table (fixed-rule + LSTM/gated-noPT/gated+struct/gated+rwalk x none/hard) and `[fig] figures/fig_dmn_pretrain.png`. Several minutes (2 pretrains over 6000-bar synthetic + 4 nested-WF runs). The LSTM row should reproduce ~0.92/0.88.

- [ ] **Step 3: Sanity-check against the success criterion**

Read the table. Record:
- **Genuine win:** `gated+struct` (better band) `net IR > 0.92` AND `NW-t > 1.5` AND `DSR > 0.8` AND clearly `gated+struct > gated+rwalk`.
- **Suspicious (regularization only):** `gated+struct ~= gated+rwalk` and both up -> the gain is generic warm-up, not a learned edge.
- **Honest null:** neither beats 0.92 -> attention does not help even with unlimited diversified pretraining.
Do not tune to force a win.

- [ ] **Step 4: Commit (driver + figure)**

```bash
git add paper5/code/run_dmn_pretrain.py
git add -f paper5/figures/fig_dmn_pretrain.png
git commit -m "feat(paper5): synthetic-pretraining ablation driver (structured vs randomwalk control)"
```

---

## Task S4: Record the result (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (paper5 Phase-3 findings block — targeted Edit; a parallel session also edits this file)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the pretraining outcome to the paper5 Phase-3 findings in `etoro/CLAUDE.md`**

Add one bullet with the measured `gated+struct` and `gated+rwalk` net IR (better band) + verdict vs LSTM 0.92 and vs each other — e.g. "Synthetic-daily pretraining (18 uncorrelated parametric series, warm-start + gate reset): gated+structured net IR <S>, gated+randomwalk <R> vs LSTM 0.92 — <genuine win / regularization-only / honest null>." Fill from Task S3's table; do not invent. Use a targeted Edit anchored on existing text.

- [ ] **Step 2: Update the memory file** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line with the result + verdict. Keep it one fact. (Memory files are outside the repo — save with the Write tool.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record synthetic-pretraining attention outcome"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 3 modules (synth_data / train_eval / run_dmn_pretrain + tests) -> Tasks S1-S4. ✓
- Spec section 4 generator (N=18 independent; structured mix trend/MR/vol/jumps; randomwalk control; via crypto_features) -> Task S1 (incl. independence/ENB + determinism + kind-differs tests). ✓
- Spec section 5 pretrain->finetune (pretrain on full synthetic, warm-start all, gate reset 0, fine-tune per fold via trainer hook; parametric => leak-free) -> Task S2 (`pretrain_model`, `make_pretrained_trainer`; gate-reset + finite tests) + Task S3 (driver wires `trainer=`). ✓
- Spec "single fixed cfg so weights load" -> Task S3 uses `PRE = GATED_GRID[0]`, grid `[PRE]` for all gated rows; pretrain with `PRE`. ✓
- Spec section 6 eval/ablation/criteria (real combined-18, both bands, nested WF + DSR + net@10bps, PPY=252, 4 rows; genuine = struct>0.92 ∧ NW-t>1.5 ∧ DSR>0.8 ∧ struct>rwalk; suspicious; honest null) -> Task S3 driver + Step 3. ✓
- Spec section 7 testing (synth shape/independence/determinism; pretrain loadable; trainer gate-reset + finite) -> Tasks S1, S2 ship each. ✓
- Spec section 8 conventions -> Context + commit steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". The `<S>/<R>/<verdict>` in S4 are experiment outputs unavailable before S3 runs; instructions say fill from the table, don't invent. Acceptable.

**3. Type consistency:** `make_synthetic(kind, n_assets, T, seed)` (S1) called in S3 with those args -> DataFrame -> `crypto_features.build` -> `(X (N,T,10), fwd, dates_ms)`. `pretrain_model(make, cfg, X_syn, fwd_syn, epochs)` (S2) returns a state dict loaded by `make_pretrained_trainer(state)` (S2) into `make_gated_hybrid(F, cfg)`; the trainer signature `(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2)` matches `nested_walkforward`'s `trainer(make, X, fwd, warm, train_hi, cfg, epochs)` call. `GATED_GRID[0]` used identically for pretrain and fine-tune so `load_state_dict` shapes match. `evaluate(..., ppy=PPY)` and `_row` dict keys (`net_ir/nw_t/dsr/durability`) consistent with prior committed code. `dc.basket_stats` returns `(corr, avg, enb)` consumed in the S1 test. ✓
```
