# Gradient-Boosted-Trees (tabular) Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sklearn HistGradientBoostingRegressor on the 10 features (a non-deep, lower-capacity replacement for the transformer/DMN) with a leak-free walk-forward, and honestly compare it to the LSTM (0.92) and the fixed rule (1.11) on combined-18.

**Architecture:** The GBT does not fit the torch `nested_walkforward`, so it gets its own leak-free walk-forward (`gbt_positions`) that produces a `(N,T)` position path, then reuses `train_eval.evaluate` for the net-of-cost metrics — identical to the DMN evaluation. The GBT predicts next-day return; predictions map to a vol-scaled, banded position (same sizing as the rule) so the comparison isolates signal quality.

**Tech Stack:** Python 3.11+, NumPy/pandas, scikit-learn (`HistGradientBoostingRegressor`, already installed), matplotlib. Tests: pytest, fully offline.

---

## Context for the implementer (read once)

cwd `etoro/`. Work in `paper5/code/` (bare-import: NO `__init__.py`; tests in `paper5/code/tests/`, run `python -m pytest` from `paper5/code/`). Prior iterations committed; offline suite passes (41 tests). Do NOT modify `paper4/` or the torch training functions in `train_eval.py` (only CALL `evaluate`, `make_folds`, `nested_walkforward`). Commits: clean `git commit -m "..."`, NO `Co-Authored-By`. Figures: `git add -f`.

**Reuse:** `crypto_features.build(close_df) -> (X (N,T,10), fwd (N,T), dates_ms)`. `train_eval.make_folds(T, warm, first_train, step) -> [(train_hi, test_hi), ...]`. `train_eval.evaluate(POS, fwd, dates_ms, test_idx, band, spread_bps=10.0, n_trials=1, short_fin=0.0, ppy=PPY)` -> dict with `net_ir/nw_t/dsr/durability/n` (applies band + equal-capital `/N` + costs to a `(N,T)` POS, sliced to `test_idx`). `train_eval.nested_walkforward(make, grid, X, fwd, folds, warm, epochs, trainer=None)` for the LSTM baseline row. `metrics.ann_ir(r, periods)` (import via the paper4 sys.path preamble). `combined_data.fetch_combined_daily()` -> real (T,18) close DataFrame. `models.make_lstm`/`LSTM_GRID`.

**sklearn:** `from sklearn.ensemble import HistGradientBoostingRegressor`; `.fit(X2d, y1d)`, `.predict(X2d)`. `from sklearn.inspection import permutation_importance` for feature importances (HistGBR has no `feature_importances_`).

**The 10 feature names (order matches `build_features`):** `["ret1","ret21","ret63","ret126","ret252","logvol","kal_vel","kal_tsig","kal_innov","bocpd"]`.

---

## File Structure

- `paper5/code/gbt_model.py` — **create**: `GBT_GRID`, `predict_to_position(pred, vol, scale)`, `gbt_positions(X, fwd, vol, fold_bounds, grid, warm) -> (POS, test_idx)`.
- `paper5/code/run_dmn_gbt.py` — **create**: comparison driver (fixed-rule / LSTM / GBT on combined-18, both bands) + feature importances + figure.
- `paper5/code/tests/test_gbt_model.py` — **create**: mapping / shape+leak-free / determinism.

---

## Task T1: GBT model + leak-free walk-forward

**Files:**
- Create: `paper5/code/gbt_model.py`
- Create: `paper5/code/tests/test_gbt_model.py`

- [ ] **Step 1: Write the failing tests**

```python
# paper5/code/tests/test_gbt_model.py
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import gbt_model


def test_predict_to_position_zero_bounded_signflip():
    vol = np.array([0.5, 0.5])
    assert np.allclose(gbt_model.predict_to_position(np.array([0.0, 0.0]), vol, 1.0), 0.0)
    big = gbt_model.predict_to_position(np.array([100.0, -100.0]), vol, 1.0)
    assert np.all(np.abs(big) <= 2.0 + 1e-9)
    assert big[0] > 0 and big[1] < 0            # sign follows the prediction


def test_gbt_positions_shape_leakfree_bounded():
    rng = np.random.default_rng(0)
    N, T, F = 4, 220, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = (0.3 * X[:, :, 0] + rng.standard_normal((N, T)) * 0.5).astype("float32") * 0.01
    vol = np.full((N, T), 0.3, dtype="float32")
    folds = gbt_model_make_folds(T)
    POS, test_idx = gbt_model.gbt_positions(X, fwd, vol, folds, warm=20)
    assert POS.shape == (N, T)
    assert np.allclose(POS[:, :folds[0][0]], 0.0)   # leak-free: train region untouched
    assert np.isfinite(POS).all()
    assert np.all(np.abs(POS) <= 2.0 + 1e-6)
    assert test_idx.min() == folds[0][0]


def test_gbt_positions_deterministic():
    rng = np.random.default_rng(1)
    N, T, F = 4, 200, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    vol = np.full((N, T), 0.3, dtype="float32")
    folds = gbt_model_make_folds(T)
    a, _ = gbt_model.gbt_positions(X, fwd, vol, folds, warm=20)
    b, _ = gbt_model.gbt_positions(X, fwd, vol, folds, warm=20)
    assert np.allclose(a, b)


def gbt_model_make_folds(T):
    # local mini fold-builder so the test is self-contained
    return [(100, 150), (150, T)]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_gbt_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gbt_model'`.

- [ ] **Step 3: Implement `gbt_model.py`**

```python
# paper5/code/gbt_model.py
"""Gradient-boosted-trees (sklearn HistGradientBoostingRegressor) on the 10 belief-state features —
a non-deep, lower-capacity alternative to the transformer/DMN. Leak-free walk-forward: per fold, fit
on the past, select the config by validation IR, refit, predict the test span, and map the predicted
next-day return to a vol-scaled position (same sizing as the fixed rule). Reuses evaluate() downstream."""
from __future__ import annotations
import sys, os
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import metrics  # paper4

GBT_GRID = [
    {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 100, "l2_regularization": 1.0},
    {"max_iter": 300, "learning_rate": 0.03, "max_leaf_nodes": 31, "min_samples_leaf": 200, "l2_regularization": 1.0},
    {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 7,  "min_samples_leaf": 300, "l2_regularization": 2.0},
]
TARGET_VOL = 0.15


def predict_to_position(pred, vol, scale):
    """Map predicted return(s) to a vol-scaled position in [-2,2]. direction = tanh(pred/scale);
    position = clip(direction * (TARGET_VOL/vol), -2, 2). Works elementwise on arrays of any shape."""
    direction = np.tanh(np.asarray(pred, float) / (scale + 1e-12))
    pos = direction * (TARGET_VOL / np.maximum(np.asarray(vol, float), 1e-6))
    return np.clip(pos, -2.0, 2.0)


def _flatten(X, fwd, lo, hi):
    """(N,T,F)+(N,T) over [lo,hi) -> rows (M,F), targets (M,), dropping non-finite rows."""
    Xr = X[:, lo:hi].reshape(-1, X.shape[2])
    yr = fwd[:, lo:hi].reshape(-1)
    m = np.isfinite(Xr).all(axis=1) & np.isfinite(yr)
    return Xr[m], yr[m]


def _ewm_rows(pos, span=5):
    """Per-asset EWM smoothing along time. pos (N, L) -> (N, L)."""
    return pd.DataFrame(pos.T).ewm(span=span, min_periods=1).mean().to_numpy().T


def _span_positions(model, X, vol, lo, hi, scale):
    """Predict [lo,hi) and map to positions (N, hi-lo) (no smoothing — used for val IR)."""
    N, _, F = X.shape
    pred = model.predict(X[:, lo:hi].reshape(-1, F)).reshape(N, hi - lo)
    return predict_to_position(pred, vol[:, lo:hi], scale)


def gbt_positions(X, fwd, vol, fold_bounds, grid=GBT_GRID, warm=252):
    """Leak-free GBT walk-forward. Returns (POS (N,T) filled on test spans only, test_idx)."""
    N, T, F = X.shape
    POS = np.zeros((N, T))
    test_idx = []
    for train_hi, test_hi in fold_bounds:
        vlo = int(warm + 0.8 * (train_hi - warm))
        Xtr, ytr = _flatten(X, fwd, warm, vlo)
        best_ir, best_cfg = -1e18, None
        for cfg in grid:
            m = HistGradientBoostingRegressor(random_state=0, **cfg).fit(Xtr, ytr)
            s = float(np.std(m.predict(Xtr))) + 1e-9
            pos_val = _span_positions(m, X, vol, vlo, train_hi, s)
            port = np.nanmean(pos_val * fwd[:, vlo:train_hi], axis=0)
            port = port[np.isfinite(port)]
            ir = metrics.ann_ir(port, 252) if len(port) else -1e18
            if np.isfinite(ir) and ir > best_ir:
                best_ir, best_cfg = ir, cfg
        if best_cfg is None:
            best_cfg = grid[0]
        Xall, yall = _flatten(X, fwd, warm, train_hi)
        model = HistGradientBoostingRegressor(random_state=0, **best_cfg).fit(Xall, yall)
        s = float(np.std(model.predict(Xall))) + 1e-9
        pos = _span_positions(model, X, vol, train_hi, test_hi, s)
        POS[:, train_hi:test_hi] = np.nan_to_num(_ewm_rows(pos, span=5))
        test_idx += list(range(train_hi, test_hi))
    return POS, np.array(test_idx)
```

- [ ] **Step 4: Run the tests**

Run: `cd paper5/code && python -m pytest tests/test_gbt_model.py -v`
Expected: PASS (3 passed). The leak-free assertion (`POS[:, :first_train]==0`) and the `|POS|<=2` bound are the key ones.

- [ ] **Step 5: Commit**

```bash
git add paper5/code/gbt_model.py paper5/code/tests/test_gbt_model.py
git commit -m "feat(paper5): gradient-boosted-trees leak-free walk-forward (HistGradientBoosting -> vol-scaled positions)"
```

---

## Task T2: Comparison driver (fixed-rule / LSTM / GBT) + feature importances

**Files:**
- Create: `paper5/code/run_dmn_gbt.py`

No unit test (needs cached real data + training). Integration entry point.

- [ ] **Step 1: Write the driver**

```python
# paper5/code/run_dmn_gbt.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tabular GBT vs deep LSTM vs fixed rule on real combined-18 (both bands, net @10bps, PPY=252).
The GBT (sklearn HistGradientBoosting) predicts next-day return from the 10 features and is sized with
the same vol-target + band as the rule. Also reports permutation feature importances. Prints the table
and saves fig_dmn_gbt.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models, gbt_model
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
FEAT_NAMES = ["ret1", "ret21", "ret63", "ret126", "ret252", "logvol",
              "kal_vel", "kal_tsig", "kal_innov", "bocpd"]


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
    vol_nt = (close.pct_change().rolling(30).std() * np.sqrt(PPY)).shift(1).to_numpy().T  # (N,T) causal
    vol_nt = np.nan_to_num(vol_nt, nan=1.0)
    print(f"[data] {close.shape[1]} assets, {T} bars; folds={len(folds)}")

    rows = [_row("fixed-rule", "hard", fixed_rule_baseline(close, dates_ms))]

    # LSTM baseline
    POS_l, _, idx_l = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds,
                                                    warm=252, epochs=300)
    for band, tag in [(0.0, "none"), (0.3, "hard")]:
        rows.append(_row("LSTM-DMN", tag, train_eval.evaluate(POS_l, fwd, dates_ms, idx_l, band,
                         spread_bps=10.0, n_trials=len(models.LSTM_GRID), ppy=PPY)))

    # GBT
    POS_g, idx_g = gbt_model.gbt_positions(X, fwd, vol_nt, folds, warm=252)
    for band, tag in [(0.0, "none"), (0.3, "hard")]:
        rows.append(_row("GBT", tag, train_eval.evaluate(POS_g, fwd, dates_ms, idx_g, band,
                         spread_bps=10.0, n_trials=len(gbt_model.GBT_GRID), ppy=PPY)))

    print(f"\n{'model':<12}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'+2022':>8}")
    print("-" * 50)
    for nm, bd, ir, t, dsr, y in rows:
        print(f"{nm:<12}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{y:>8}")

    # feature importances: refit one GBT on the whole real panel, permutation importance
    Xall, yall = gbt_model._flatten(X, fwd, 252, T)
    gb = HistGradientBoostingRegressor(random_state=0, **gbt_model.GBT_GRID[0]).fit(Xall, yall)
    sub = np.random.default_rng(0).choice(len(Xall), size=min(20000, len(Xall)), replace=False)
    imp = permutation_importance(gb, Xall[sub], yall[sub], n_repeats=5, random_state=0)
    order = np.argsort(imp.importances_mean)[::-1]
    print("\n[feature importance] (permutation, higher = more used)")
    for i in order:
        print(f"  {FEAT_NAMES[i]:<10} {imp.importances_mean[i]:+.5f}")

    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    palette = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "GBT": "#16a34a"}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(labels, irs, color=[palette[r[0]] for r in rows])
    ax.axhline(0.92, ls="--", color="#2563eb", lw=1, label="LSTM 0.92")
    ax.axhline(1.11, ls="--", color="#64748b", lw=1, label="rule 1.11")
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR @10bps"); ax.set_title("GBT (tabular) vs LSTM vs rule (combined 18, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_gbt.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_gbt.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the driver end-to-end**

Run: `cd paper5/code && python -u run_dmn_gbt.py`
Expected: a data line, the comparison table (fixed-rule + LSTM/GBT x none/hard), a ranked feature-importance list, and `[fig] figures/fig_dmn_gbt.png`. The LSTM rows should reproduce ~0.92/0.88. GBT is fast (sklearn, no epochs); the LSTM is the slow part.

- [ ] **Step 3: Sanity-check against the success criterion**

Record from the table whether GBT (better band) `net IR > 0.92` (∧ NW-t>1.5, DSR>0.8) -> tabular beats deep; `~0.92` -> equivalent (simpler model preferred); `<0.92` -> deep holds; `>1.11` -> first ML to beat the rule. Note the top features. Do not tune to force an outcome.

- [ ] **Step 4: Commit (driver + figure)**

```bash
git add paper5/code/run_dmn_gbt.py
git add -f paper5/figures/fig_dmn_gbt.png
git commit -m "feat(paper5): GBT vs LSTM vs rule comparison driver + feature importances"
```

---

## Task T3: Record the result (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (paper5 Phase-3 findings — targeted Edit; a parallel session also edits this file)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the GBT outcome to the paper5 findings in `etoro/CLAUDE.md`**

Add one bullet with the measured GBT net IR (better band) vs LSTM 0.92 / rule 1.11, the verdict
(tabular beats / matches / loses to deep), and the top feature(s). Fill from Task T2's output; do not
invent. Use a targeted Edit anchored on existing text.

- [ ] **Step 2: Update the memory file** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line: the GBT result + verdict + top features. Keep it one fact. (Memory files are outside
the repo — save with the Write tool.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record GBT tabular model outcome"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 2 modules (gbt_model / run_dmn_gbt + tests; own walk-forward reusing evaluate; paper4 + torch training untouched) -> Tasks T1-T3. ✓
- Spec section 3 model+mapping (HistGBR predicts return; `predict_to_position` = tanh(pred/scale) * (0.15/vol), clip +-2; per-fold fit-on-train, select by val IR, refit, predict test, scale from train, ewm; leak-free; `random_state=0`) -> Task T1 (`GBT_GRID`, `predict_to_position`, `gbt_positions`). ✓
- Spec section 4 eval/comparison (combined-18, both bands, evaluate, fixed-rule + LSTM + GBT, feature importances via permutation, figure, success criterion) -> Task T2 + Step 3. ✓
- Spec section 5 testing (shape+leak-free+bounded, mapping zero/bounded/signflip, determinism) -> Task T1 tests. ✓
- Spec section 6 conventions -> Context + commit steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". `<...>` verdict numbers in T3 are experiment outputs unavailable before T2; instructions say fill from output, don't invent. Acceptable.

**3. Type consistency:** `predict_to_position(pred, vol, scale)` defined T1, used in `_span_positions` and tested. `gbt_positions(X, fwd, vol, fold_bounds, grid=GBT_GRID, warm=252) -> (POS, test_idx)` — driver calls `gbt_positions(X, fwd, vol_nt, folds, warm=252)` and consumes `(POS_g, idx_g)`. `vol_nt` is `(N,T)` (transposed from the `(T,N)` pandas). `train_eval.evaluate(POS, fwd, dates_ms, test_idx, band, spread_bps, n_trials, ppy)` consumes both POS paths identically; `_row` reads `net_ir/nw_t/dsr/durability`. `gbt_model._flatten` reused in the driver for the importance refit. `metrics.ann_ir(port, 252)` for val IR. All consistent. ✓
```
