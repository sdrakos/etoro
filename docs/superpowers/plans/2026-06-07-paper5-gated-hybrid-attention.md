# Gated / Frozen Hybrid Attention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make attention additive and safe on top of the LSTM — a scalar-gated residual (`h + g*attention(h)`, `g` init 0) plus a two-stage frozen-LSTM trainer — and honestly test (combined 18-asset, leak-free, net @10bps) whether it finally beats the LSTM-DMN (0.92) instead of destroying it (the naive hybrid scored -0.57).

**Architecture:** Extend the existing paper5 modules (paper4 untouched). Add `GatedHybridMomentumNetwork` to `models.py`. Behavior-preservingly refactor `train_eval._train_fold` into reusable `_prep_tensors` + `_run_epochs`, then add `_train_fold_two_stage` and a `trainer=` hook on `nested_walkforward`. A new driver runs the five-model ablation.

**Tech Stack:** Python 3.11+, PyTorch, NumPy/pandas, matplotlib. Tests: pytest, fully offline (synthetic tensors, no network).

---

## Context for the implementer (read once)

cwd `etoro/`. Work in `paper5/code/` (bare-import: NO `__init__.py`; tests in `paper5/code/tests/`, run with `python -m pytest` from `paper5/code/`). Prior iterations are committed; the offline suite currently passes (23 tests). Do NOT modify `paper4/`. Commits: clean `git commit -m "..."`, NO `Co-Authored-By`. Figures: `git add -f`.

**`models.py` already has:** `_PositionalEncoding`, `_block_local_encode(enc, pos, h, window)` (shared block-local causal encoder over an embedded `(N,T,d)` sequence), `MomentumTransformer` (pure, with `norm_first`), `HybridMomentumNetwork` (naive LSTM+attention, the -0.57 contrast), factories `make_lstm`/`make_transformer`/`make_hybrid`, grids `LSTM_GRID`/`TRANSF_GRID`/`HYBRID_GRID`.

**`train_eval.py` already has:** `PPY=365`, `TRAIN_COST=1e-3`, `BASE_LR=1e-3`, `warmup_lambda(step, warmup)`, `make_folds`, `_train_fold(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2)`, `_predict`, `nested_walkforward(make, grid, X, fwd, fold_bounds, warm=252, epochs=300)`, `evaluate(POS, fwd, dates_ms, test_idx, band, spread_bps=10.0, n_trials=1, short_fin=0.0, ppy=PPY)`. The current `_train_fold` body is: `torch.manual_seed(0)` -> build val split + standardized train/val tensors -> `make(...)` -> Adam(`lr=BASE_LR`, `weight_decay=cfg["wd"]`) -> `LambdaLR` warmup -> loop `epochs` doing `opt.step(); sched.step()` with periodic (every 10) validation capture of the best state -> load best -> return `(net, mu, sd, best)`.

**Key facts:** models map `x (N,T,10) -> (N,T)` in `[-1,1]`, trained with `dmn.sharpe_loss(pred, fwd, cost=TRAIN_COST)`. `torch.manual_seed(0)` at the start of each train function is required for determinism. The two-stage trainer only works on a model exposing `.lstm`, `.enc`, `.gate`, `.head` (i.e. `GatedHybridMomentumNetwork`).

---

## File Structure

- `paper5/code/models.py` — **modify**: add `GatedHybridMomentumNetwork`, `make_gated_hybrid`, `GATED_GRID`.
- `paper5/code/train_eval.py` — **modify**: extract `_prep_tensors` + `_run_epochs` (behavior-preserving), add `_set_requires_grad` + `_train_fold_two_stage`, add `trainer=` param to `nested_walkforward`.
- `paper5/code/run_dmn_gated.py` — **create**: five-model ablation driver on combined-18, both bands.
- `paper5/code/tests/test_models.py` — **modify**: gated-hybrid tests.
- `paper5/code/tests/test_train_eval.py` — **modify**: freeze + two-stage tests.

---

## Task G1: GatedHybridMomentumNetwork + factory + grid

**Files:**
- Modify: `paper5/code/models.py`
- Test: `paper5/code/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `paper5/code/tests/test_models.py`:

```python
def test_gated_hybrid_output_shape_and_range():
    net = models.make_gated_hybrid(10, models.GATED_GRID[0]).eval()
    with torch.no_grad():
        net.gate.fill_(0.5)
    x = torch.randn(4, 30, 10)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (4, 30)
    assert float(out.min()) >= -1.0 and float(out.max()) <= 1.0


def test_gated_hybrid_gate_init_zero():
    net = models.make_gated_hybrid(10, models.GATED_GRID[0])
    assert float(net.gate) == 0.0


def test_gated_hybrid_gate_zero_isolates_attention():
    # with gate=0, the output must NOT depend on the attention encoder's weights.
    torch.manual_seed(0)
    net = models.make_gated_hybrid(10, models.GATED_GRID[0]).eval()
    x = torch.randn(3, 20, 10)
    with torch.no_grad():
        o1 = net(x)
        for p in net.enc.parameters():
            p.add_(1.0)                      # perturb attention; gate=0 => no effect
        o2 = net(x)
    assert torch.allclose(o1, o2, atol=1e-6)


def test_gated_hybrid_is_causal():
    # with the gate active, perturbing the last timestep must not change earlier outputs.
    torch.manual_seed(0)
    net = models.make_gated_hybrid(10, models.GATED_GRID[0]).eval()
    with torch.no_grad():
        net.gate.fill_(1.0)
    x = torch.randn(2, 16, 10)
    with torch.no_grad():
        o1 = net(x)
        x2 = x.clone(); x2[:, -1, :] += 5.0
        o2 = net(x2)
    assert torch.allclose(o1[:, :-1], o2[:, :-1], atol=1e-5)


def test_gated_grid_nheads_divide_hidden():
    for cfg in models.GATED_GRID:
        assert cfg["hidden"] % cfg["nheads"] == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_models.py -k gated -v`
Expected: FAIL with `AttributeError: module 'models' has no attribute 'make_gated_hybrid'`.

- [ ] **Step 3: Implement the gated hybrid**

In `paper5/code/models.py`, add after `HybridMomentumNetwork`:

```python
class GatedHybridMomentumNetwork(nn.Module):
    """Like the hybrid, but attention is a SCALAR-GATED RESIDUAL: out = h + g * attention(h), where
    g is a single learnable scalar initialized to 0. At init g=0 so the model IS an LSTM->head
    (~the 0.92 model) with attention invisible; training raises g only if attention helps. Floor is
    the LSTM, upside only. Leak-free: LSTM causal + block-local-causal attention."""
    def __init__(self, n_features, hidden=16, nheads=2, dropout=0.1, window=256):
        super().__init__()
        self.window = window
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.pos = _PositionalEncoding(hidden)
        layer = nn.TransformerEncoderLayer(hidden, nheads, dim_feedforward=4 * hidden,
                                           dropout=dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, 1)
        self.gate = nn.Parameter(torch.zeros(1))                  # scalar gate, init 0
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):                # x (N,T,F) -> (N,T) in [-1,1]
        h, _ = self.lstm(x)
        a = _block_local_encode(self.enc, self.pos, h, self.window)
        h = h + self.gate * a                                     # gated residual
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)
```

And add the grid + factory near the other factories:

```python
GATED_GRID = [
    {"hidden": 16, "nheads": 2, "dropout": 0.1, "wd": 1e-3, "warmup": 50},
    {"hidden": 16, "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
    {"hidden": 8,  "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
]


def make_gated_hybrid(n_features, cfg):
    return GatedHybridMomentumNetwork(n_features, hidden=cfg["hidden"], nheads=cfg["nheads"],
                                      dropout=cfg["dropout"], window=cfg.get("window", 256))
```

- [ ] **Step 4: Run the model tests**

Run: `cd paper5/code && python -m pytest tests/test_models.py -v`
Expected: PASS (all gated tests + all prior). The isolation and causal tests are the critical ones; do not weaken them.

- [ ] **Step 5: Commit**

```bash
git add paper5/code/models.py paper5/code/tests/test_models.py
git commit -m "feat(paper5): GatedHybridMomentumNetwork (scalar-gated residual attention, init 0)"
```

---

## Task G2: Behavior-preserving refactor of `_train_fold`

**Files:**
- Modify: `paper5/code/train_eval.py`
- Test: `paper5/code/tests/test_train_eval.py` (existing tests are the guard)

This extracts two helpers WITHOUT changing `_train_fold`'s observable behavior (so the LSTM 0.92 and naive-hybrid -0.57 still reproduce). The existing nested-WF + warmup tests are the regression guard.

- [ ] **Step 1: Run the existing suite to capture the green baseline**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -v`
Expected: PASS (record the count, e.g. 4 passed).

- [ ] **Step 2: Refactor — add `_prep_tensors` and `_run_epochs`, rewrite `_train_fold` to use them**

In `paper5/code/train_eval.py`, replace the current `_train_fold` function with these three definitions (same order of operations, same seed, so behavior is identical):

```python
def _prep_tensors(X, fwd, lo, hi, val_frac):
    """Build the standardized train/val tensors for [lo,hi). No RNG (keeps seeding deterministic)."""
    vlo = int(lo + (1 - val_frac) * (hi - lo))
    Xt = torch.tensor(X[:, lo:hi], dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True)
    sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (torch.tensor(X[:, lo:vlo], dtype=torch.float32) - mu) / sd
    ftr = torch.tensor(fwd[:, lo:vlo], dtype=torch.float32)
    Xv = (torch.tensor(X[:, vlo:hi], dtype=torch.float32) - mu) / sd
    fv = torch.tensor(fwd[:, vlo:hi], dtype=torch.float32)
    return mu, sd, Xtr, ftr, Xv, fv


def _run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs, best=float("inf"), best_state=None):
    """Run `epochs` full-batch training steps; capture the best-validation state every 10 epochs.
    Threads (best, best_state) so a caller can accumulate the best across multiple stages."""
    for e in range(epochs):
        net.train(); opt.zero_grad()
        sharpe_loss(net(Xtr), ftr, cost=TRAIN_COST).backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        sched.step()
        if e % 10 == 0:
            net.eval()
            with torch.no_grad():
                v = float(sharpe_loss(net(Xv), fv, cost=TRAIN_COST))
            if v < best:
                best = v
                best_state = {k: val.clone() for k, val in net.state_dict().items()}
    return best, best_state


def _train_fold(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
    """Train on [lo,hi) with the last val_frac as validation (early stop). Standardisation fit on
    train only. Returns (net, mu, sd, best_val_loss)."""
    torch.manual_seed(0)
    mu, sd, Xtr, ftr, Xv, fv = _prep_tensors(X, fwd, lo, hi, val_frac)
    net = make(X.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, cfg.get("warmup", 0)))
    best, best_state = _run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs)
    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    return net, mu, sd, best
```

- [ ] **Step 3: Run the suite — behavior must be unchanged**

Run: `cd paper5/code && python -m pytest tests/ -v`
Expected: PASS, same count as before the refactor (the refactor is behavior-preserving).

- [ ] **Step 4: Commit**

```bash
git add paper5/code/train_eval.py
git commit -m "refactor(paper5): extract _prep_tensors + _run_epochs (behavior-preserving)"
```

---

## Task G3: Two-stage frozen trainer + nested_walkforward trainer hook

**Files:**
- Modify: `paper5/code/train_eval.py`
- Test: `paper5/code/tests/test_train_eval.py`

- [ ] **Step 1: Write the failing tests**

Add to `paper5/code/tests/test_train_eval.py` (it already imports `train_eval`, `models`, `numpy as np`):

```python
def test_set_requires_grad_freezes_correctly():
    net = models.make_gated_hybrid(10, models.GATED_GRID[0])
    train_eval._set_requires_grad(net, lstm=True, attn=False)
    assert all(p.requires_grad for p in net.lstm.parameters())
    assert all(not p.requires_grad for p in net.enc.parameters())
    assert net.gate.requires_grad is False
    train_eval._set_requires_grad(net, lstm=False, attn=True)
    assert all(not p.requires_grad for p in net.lstm.parameters())
    assert all(p.requires_grad for p in net.enc.parameters())
    assert net.gate.requires_grad is True


def test_two_stage_trainer_returns_finite_and_right_shape():
    import torch
    rng = np.random.default_rng(0)
    N, T, F = 3, 120, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    net, mu, sd, best = train_eval._train_fold_two_stage(
        models.make_gated_hybrid, X, fwd, 0, T, models.GATED_GRID[0], epochs=6)
    assert np.isfinite(best)
    with torch.no_grad():
        out = net((torch.tensor(X[:, :20], dtype=torch.float32) - mu) / sd)
    assert out.shape == (3, 20)


def test_nested_wf_accepts_two_stage_trainer():
    rng = np.random.default_rng(0)
    N, T, F = 3, 160, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    folds = train_eval.make_folds(T, warm=20, first_train=100, step=40)
    POS, chosen, idx = train_eval.nested_walkforward(
        models.make_gated_hybrid, models.GATED_GRID[:1], X, fwd, folds,
        warm=20, epochs=4, trainer=train_eval._train_fold_two_stage)
    assert np.allclose(POS[:, :100], 0.0)        # leak-free: train region untouched
    assert idx.min() == 100
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -k "two_stage or requires_grad" -v`
Expected: FAIL with `AttributeError: module 'train_eval' has no attribute '_set_requires_grad'`.

- [ ] **Step 3: Implement the freeze helper + two-stage trainer + trainer hook**

In `paper5/code/train_eval.py`, add after `_train_fold`:

```python
def _set_requires_grad(net, lstm, attn):
    """Freeze/unfreeze groups of a GatedHybridMomentumNetwork. The head always trains."""
    for p in net.lstm.parameters():
        p.requires_grad_(lstm)
    for p in net.enc.parameters():
        p.requires_grad_(attn)
    net.gate.requires_grad_(attn)
    for p in net.head.parameters():
        p.requires_grad_(True)


def _train_fold_two_stage(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
    """Two-stage training for the gated hybrid: stage 1 trains lstm+head with attention frozen
    (reaches ~the LSTM result); stage 2 freezes the lstm and trains attention(enc+gate)+head on the
    fixed LSTM features. The best-validation state is accumulated ACROSS both stages, so if stage 2
    only hurts, the stage-1 (LSTM) state is kept -> floor is the LSTM. Returns (net, mu, sd, best)."""
    torch.manual_seed(0)
    mu, sd, Xtr, ftr, Xv, fv = _prep_tensors(X, fwd, lo, hi, val_frac)
    net = make(X.shape[2], cfg)
    warmup = cfg.get("warmup", 0)
    e1 = epochs // 2
    e2 = epochs - e1

    _set_requires_grad(net, lstm=True, attn=False)                # stage 1: LSTM + head
    opt1 = torch.optim.Adam([p for p in net.parameters() if p.requires_grad],
                            lr=BASE_LR, weight_decay=cfg["wd"])
    sch1 = torch.optim.lr_scheduler.LambdaLR(opt1, lr_lambda=lambda e: warmup_lambda(e, warmup))
    best, best_state = _run_epochs(net, opt1, sch1, Xtr, ftr, Xv, fv, e1)

    _set_requires_grad(net, lstm=False, attn=True)                # stage 2: attention + head
    opt2 = torch.optim.Adam([p for p in net.parameters() if p.requires_grad],
                            lr=BASE_LR, weight_decay=cfg["wd"])
    sch2 = torch.optim.lr_scheduler.LambdaLR(opt2, lr_lambda=lambda e: warmup_lambda(e, warmup))
    best, best_state = _run_epochs(net, opt2, sch2, Xtr, ftr, Xv, fv, e2, best, best_state)

    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    return net, mu, sd, best
```

Then change `nested_walkforward`'s signature to add a `trainer` hook and use it. Replace the `def nested_walkforward(...)` line and the inner `_train_fold(...)` call:

```python
def nested_walkforward(make, grid, X, fwd, fold_bounds, warm=252, epochs=300, trainer=None):
    """For each fold, pick the cfg with best validation loss (never touching test), predict on the
    test span. `trainer` defaults to _train_fold; pass _train_fold_two_stage for the frozen variant.
    Returns (POS (N,T) filled on test spans only, chosen_cfgs, test_idx)."""
    trainer = trainer or _train_fold
    N, T, _ = X.shape
    POS = np.zeros((N, T))
    chosen, test_idx = [], []
    for train_hi, test_hi in fold_bounds:
        best, pick, picked = float("inf"), None, None
        for cfg in grid:
            net, mu, sd, vloss = trainer(make, X, fwd, warm, train_hi, cfg, epochs)
            if vloss < best:
                best, pick, picked = vloss, cfg, (net, mu, sd)
        chosen.append(pick)
        POS[:, train_hi:test_hi] = _predict(*picked, X, train_hi, test_hi)
        test_idx += list(range(train_hi, test_hi))
    return POS, chosen, np.array(test_idx)
```

(Keep the rest of `nested_walkforward`'s body identical to what is shown.)

- [ ] **Step 4: Run the tests + full suite**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -v`
Expected: PASS (freeze + two-stage + trainer-hook tests + all prior).

Run: `cd paper5/code && python -m pytest tests/ -v`
Expected: PASS (entire offline suite).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/train_eval.py paper5/code/tests/test_train_eval.py
git commit -m "feat(paper5): two-stage frozen-LSTM trainer + nested_walkforward trainer hook"
```

---

## Task G4: Driver — five-model ablation on combined 18

**Files:**
- Create: `paper5/code/run_dmn_gated.py`

No unit test (needs cached data + heavy training). Integration entry point.

- [ ] **Step 1: Write the driver**

```python
# paper5/code/run_dmn_gated.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iteration 3: can attention, made SAFE, finally beat the LSTM (0.92)? Runs fixed-rule / LSTM /
naive-hybrid (-0.57 contrast) / gated (A) / frozen (B) on the combined 18-asset basket, both bands,
leak-free nested WF, net @10bps, PPY=252. Prints the table and saves fig_dmn_gated.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252


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
    print(f"[data] {close.shape[1]} assets, {T} bars, {close.index[0].date()}..{close.index[-1].date()}")
    print(f"[wf] {len(folds)} folds, test from idx {folds[0][0]}")

    rows = [_row("fixed-rule", "hard", fixed_rule_baseline(close, dates_ms))]

    runs = [
        ("LSTM-DMN",    models.make_lstm,         models.LSTM_GRID,   None),
        ("naive-hybrid", models.make_hybrid,      models.HYBRID_GRID, None),
        ("gated-A",     models.make_gated_hybrid, models.GATED_GRID,  None),
        ("frozen-B",    models.make_gated_hybrid, models.GATED_GRID,  train_eval._train_fold_two_stage),
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
    palette = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "naive-hybrid": "#dc2626",
               "gated-A": "#16a34a", "frozen-B": "#0d9488"}
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.bar(labels, irs, color=[palette[r[0]] for r in rows])
    ax.axhline(lstm_best, ls="--", color="#2563eb", lw=1, label=f"LSTM best {lstm_best:.2f}")
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR @10bps"); ax.set_title("Gated / frozen attention vs LSTM (combined 18, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_gated.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_gated.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the driver end-to-end**

Run: `cd paper5/code && python -u run_dmn_gated.py`
Expected: a data line, a folds line, a 9-row table (fixed-rule + LSTM/naive-hybrid/gated-A/frozen-B x none/hard), and `[fig] figures/fig_dmn_gated.png`. Several minutes. The LSTM (~0.92/0.88) and naive-hybrid (~-0.57/-0.55) rows should reproduce (sanity).

- [ ] **Step 3: Sanity-check against the success criterion**

Read the table. Record whether gated-A or frozen-B (better band) meets ALL of `net IR > 0.92`, `NW-t > 1.5`, `DSR > 0.8`. If yes -> attention finally adds value. If ~0.92 -> "does not add but no longer hurts". If materially **below 0.92** -> a bug (the gate floor is the LSTM); investigate before recording. Do not tune to force a win.

- [ ] **Step 4: Commit (driver + figure)**

```bash
git add paper5/code/run_dmn_gated.py
git add -f paper5/figures/fig_dmn_gated.png
git commit -m "feat(paper5): gated/frozen attention ablation driver (combined 18)"
```

---

## Task G5: Record the result (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (the paper5 Phase-3 findings block — use a targeted Edit; a parallel session also edits this file)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the gated/frozen outcome to the paper5 Phase-3 findings in `etoro/CLAUDE.md`**

Add one bullet stating the measured gated-A and frozen-B net IR (better band) + verdict vs LSTM 0.92 — e.g. "Gated residual (g init 0) / frozen two-stage attention: net IR <A>/<B> — <added value / matched 0.92 / floor held>; the safe-attention fix <did/did not> beat the LSTM. See `run_dmn_gated.py`." Fill from Task G4's table; do not invent numbers. Use a targeted Edit anchored on existing text (do not rewrite the section).

- [ ] **Step 2: Update the memory file** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line with the gated/frozen result + verdict. Keep it one fact. (Memory files are outside the repo — save with the Write tool, not committed here.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record gated/frozen attention outcome"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 2 modules (models/train_eval/run_dmn_gated + tests) -> Tasks G1-G5 touch exactly those. ✓
- Spec section 3 GatedHybrid (scalar gate init 0, residual `h+g*attn`, reuse `_block_local_encode`, `norm_first=True`, make_gated_hybrid + GATED_GRID, causal) -> Task G1 (incl. gate-init/isolation/causal/nheads tests). ✓
- Spec section 4 two-stage trainer (stage1 freeze enc+gate train lstm+head; stage2 freeze lstm train attn+head; accumulate best across stages = floor; shared inner helper; `nested_walkforward` `trainer=` hook) -> Task G2 (extract `_run_epochs`/`_prep_tensors`) + Task G3 (`_set_requires_grad`, `_train_fold_two_stage`, trainer hook, freeze + two-stage + hook tests). ✓
- Spec "default path unchanged / LSTM 0.92 & naive -0.57 reproduce" -> Task G2 is explicitly behavior-preserving (guarded by full suite); Task G4 Step 2 re-checks reproduction. ✓
- Spec section 5 eval/ablation/criterion (combined 18, both bands, nested WF + DSR + net@10bps, PPY=252, 5 models incl. naive contrast; success >0.92 ∧ NW-t>1.5 ∧ DSR>0.8; <0.92 = bug) -> Task G4 driver + Step 3 check. ✓
- Spec section 6 testing (gated shape/range, gate init 0, gate isolation, gated causal; freeze helper, two-stage finite) -> Tasks G1, G3 ship each. ✓
- Spec section 7 conventions -> Context section + commit steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". The `<A>/<B>/<verdict>` in G5 are experiment outputs unavailable before G4 runs; instructions say fill from the printed table, don't invent. Acceptable.

**3. Type consistency:** `GatedHybridMomentumNetwork` exposes `.lstm/.enc/.gate/.head` — used by `_set_requires_grad` (G3) and the gate tests (G1). `make_gated_hybrid(n_features, cfg)` reads `hidden/nheads/dropout` + `cfg.get("window",256)`; `GATED_GRID` provides those + `wd`/`warmup`. `_run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs, best=inf, best_state=None)` (G2) called by `_train_fold` (G2) and `_train_fold_two_stage` (G3) with matching args. `_prep_tensors(X, fwd, lo, hi, val_frac)` returns `(mu, sd, Xtr, ftr, Xv, fv)` consumed identically in both trainers. `nested_walkforward(..., trainer=None)` (G3) defaults to `_train_fold`; the driver (G4) passes `trainer=train_eval._train_fold_two_stage` for frozen-B and `None` otherwise. `evaluate(..., ppy=PPY)` matches the committed signature. ✓
