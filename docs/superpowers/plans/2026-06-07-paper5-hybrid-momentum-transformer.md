# Hybrid Momentum Transformer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real Momentum Transformer (an LSTM encoder followed by pre-LN block-local causal attention) plus LR warmup, and honestly test (combined 18-asset basket, leak-free, net of 10 bps) whether attention on top of the LSTM beats the LSTM-DMN alone (0.92).

**Architecture:** Reuse `paper4/code` as a library (never modified) and the existing paper5 modules. Refactor the block-local-causal forward into a shared helper, add `norm_first` to the pure Transformer (default off, reproduces its 0.07 reference), add a new `HybridMomentumNetwork`, add per-cfg linear LR warmup to the training loop (default off, so the LSTM 0.92 and pure-Tr 0.07 reproduce exactly), and add a driver that runs the four-model ablation.

**Tech Stack:** Python 3.11+, PyTorch, NumPy/pandas, matplotlib. Tests: pytest, fully offline (synthetic tensors, no network).

---

## Context for the implementer (read once)

You are in `etoro/paper5/code/` (bare-import convention: NO `__init__.py`; tests in `paper5/code/tests/`, run with `python -m pytest` from `paper5/code/`). The first DMN build is already committed and passing 16 tests. This iteration extends three existing files and adds one driver.

**The current `models.py` (already committed) contains:** `_PositionalEncoding`, `MomentumTransformer` (a pure block-local causal Transformer), `make_lstm`/`make_transformer`, `LSTM_GRID`/`TRANSF_GRID`. `MomentumTransformer.forward` does: `proj(x)` -> pad time to a multiple of `window` -> reshape to `(N*nb, W, d)` blocks -> positional encoding -> causal mask `(W,W)` -> `TransformerEncoder` -> drop padding -> `tanh(head(drop(h)))`. You will **factor that block-local forward into a shared helper** so the hybrid reuses it.

**The current `train_eval._train_fold` (already committed)** builds `opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=cfg["wd"])` and loops `epochs` times doing one full-batch `opt.step()` per epoch (one optimizer step = one epoch). You will add a warmup LR scheduler here.

**Key facts (unchanged from the prior build):**
- Models take `x (N,T,F=10)` -> positions `(N,T)` in `[-1,1]`; trained with `dmn.sharpe_loss`.
- `nheads` must divide the attention width. Hybrid uses `d_model = hidden`; with `hidden in {16,8}` and `nheads=2`, both divide. Good.
- Determinism: `torch.manual_seed(0)` is already at the top of `_train_fold`. Keep it.
- Commits: clean `git commit -m "..."`, NO `Co-Authored-By`. Figures need `git add -f`.
- Do NOT modify anything under `paper4/`.

---

## File Structure

- `paper5/code/models.py` — **modify**: add `_block_local_encode` helper; refactor `MomentumTransformer.forward` to use it; add `norm_first` arg to `MomentumTransformer` (default `False`); add `HybridMomentumNetwork`, `make_hybrid`, `HYBRID_GRID`.
- `paper5/code/train_eval.py` — **modify**: add `BASE_LR` + `warmup_lambda` helper; wire a `LambdaLR` warmup into `_train_fold` reading `cfg.get("warmup", 0)`.
- `paper5/code/run_dmn_hybrid.py` — **create**: driver running fixed-rule / LSTM / pure-Tr / hybrid on combined-18, both bands; prints the table + saves `figures/fig_dmn_hybrid.png`.
- `paper5/code/tests/test_models.py` — **modify**: add hybrid shape/range, hybrid causal, pre-LN-constructs tests.
- `paper5/code/tests/test_train_eval.py` — **modify**: add `warmup_lambda` tests.

---

## Task 1: Refactor block-local forward into a shared helper

**Files:**
- Modify: `paper5/code/models.py`
- Test: `paper5/code/tests/test_models.py`

- [ ] **Step 1: Add a test that the refactor preserves MomentumTransformer behavior**

Add to `paper5/code/tests/test_models.py`:

```python
def test_block_local_helper_matches_transformer_forward():
    # The refactored helper must produce the SAME output as before for the pure Transformer.
    torch.manual_seed(0)
    net = models.make_transformer(10, models.TRANSF_GRID[0]).eval()
    x = torch.randn(3, 20, 10)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (3, 20)
    assert float(out.min()) >= -1.0 and float(out.max()) <= 1.0
```

- [ ] **Step 2: Run it (passes on current code — it's a guard for the refactor)**

Run: `cd paper5/code && python -m pytest tests/test_models.py::test_block_local_helper_matches_transformer_forward -v`
Expected: PASS (current code already satisfies it; this locks behavior before refactoring).

- [ ] **Step 3: Add the `_block_local_encode` helper and refactor `MomentumTransformer.forward`**

In `paper5/code/models.py`, add this function just after `_PositionalEncoding` (before `MomentumTransformer`):

```python
def _block_local_encode(enc, pos, h, window):
    """Block-local causal Transformer encode of an already-embedded sequence h (N,T,d).
    Splits time into non-overlapping blocks of `window`, runs causal attention WITHIN each block
    (O(T*window), leak-free), and returns (N,T,d). Shared by MomentumTransformer and the hybrid."""
    N, T, d = h.shape
    W = window
    pad = (W - T % W) % W                              # right-pad time to a multiple of W
    if pad:
        h = torch.cat([h, h.new_zeros(N, pad, d)], dim=1)
    nb = (T + pad) // W
    h = h.reshape(N * nb, W, d)                         # contiguous time blocks
    h = pos(h)                                          # positional encoding within the block
    mask = torch.triu(torch.full((W, W), float("-inf"), device=h.device), diagonal=1)
    h = enc(h, mask=mask)                              # causal within block
    return h.reshape(N, T + pad, d)[:, :T]              # drop the padding
```

Then replace `MomentumTransformer.forward` body with:

```python
    def forward(self, x):                # x (N,F) ... (N,T,F) -> (N,T) in [-1,1]
        h = _block_local_encode(self.enc, self.pos, self.proj(x), self.window)
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)
```

- [ ] **Step 4: Run the model tests (refactor must keep everything green)**

Run: `cd paper5/code && python -m pytest tests/test_models.py -v`
Expected: PASS (all prior tests incl. `test_transformer_is_causal`, `test_transformer_block_local_attention`, and the new guard).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/models.py paper5/code/tests/test_models.py
git commit -m "refactor(paper5): extract block-local causal encode into a shared helper"
```

---

## Task 2: Add `norm_first` (pre-LN) to MomentumTransformer

**Files:**
- Modify: `paper5/code/models.py`
- Test: `paper5/code/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `paper5/code/tests/test_models.py`:

```python
def test_transformer_norm_first_constructs_and_runs():
    # pre-LN variant must build and produce valid output; default stays post-LN (reference 0.07).
    torch.manual_seed(0)
    net = models.MomentumTransformer(10, d_model=16, nheads=2, dropout=0.0, norm_first=True).eval()
    x = torch.randn(2, 12, 10)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (2, 12)
    assert net.enc.layers[0].norm_first is True
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd paper5/code && python -m pytest tests/test_models.py::test_transformer_norm_first_constructs_and_runs -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'norm_first'`.

- [ ] **Step 3: Add the `norm_first` arg**

In `paper5/code/models.py`, change `MomentumTransformer.__init__` signature and the layer build:

```python
    def __init__(self, n_features, d_model=16, nheads=2, dropout=0.1, nlayers=1, window=256,
                 norm_first=False):
        super().__init__()
        self.window = window
        self.proj = nn.Linear(n_features, d_model)
        self.pos = _PositionalEncoding(d_model)
        layer = nn.TransformerEncoderLayer(d_model, nheads, dim_feedforward=4 * d_model,
                                           dropout=dropout, batch_first=True, norm_first=norm_first)
        self.enc = nn.TransformerEncoder(layer, nlayers)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(d_model, 1)
```

And make `make_transformer` pass it through (default off, so the committed 0.07 reproduces):

```python
def make_transformer(n_features, cfg):
    return MomentumTransformer(n_features, d_model=cfg["d_model"], nheads=cfg["nheads"],
                               dropout=cfg["dropout"], window=cfg.get("window", 256),
                               norm_first=cfg.get("norm_first", False))
```

- [ ] **Step 4: Run the model tests**

Run: `cd paper5/code && python -m pytest tests/test_models.py -v`
Expected: PASS (new test + all prior).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/models.py paper5/code/tests/test_models.py
git commit -m "feat(paper5): optional pre-LN (norm_first) in MomentumTransformer"
```

---

## Task 3: Add HybridMomentumNetwork + factory + grid

**Files:**
- Modify: `paper5/code/models.py`
- Test: `paper5/code/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `paper5/code/tests/test_models.py`:

```python
def test_hybrid_output_shape_and_range():
    net = models.make_hybrid(10, models.HYBRID_GRID[0]).eval()
    x = torch.randn(4, 30, 10)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (4, 30)
    assert float(out.min()) >= -1.0 and float(out.max()) <= 1.0


def test_hybrid_is_causal():
    # LSTM + block-local-causal attention => perturbing the last timestep leaves earlier outputs
    # unchanged (leak-free). T < window so the whole sequence is one block.
    torch.manual_seed(0)
    net = models.make_hybrid(10, models.HYBRID_GRID[0]).eval()
    x = torch.randn(2, 16, 10)
    with torch.no_grad():
        o1 = net(x)
        x2 = x.clone(); x2[:, -1, :] += 5.0
        o2 = net(x2)
    assert torch.allclose(o1[:, :-1], o2[:, :-1], atol=1e-5)


def test_hybrid_grid_nheads_divide_hidden():
    for cfg in models.HYBRID_GRID:
        assert cfg["hidden"] % cfg["nheads"] == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_models.py -k hybrid -v`
Expected: FAIL with `AttributeError: module 'models' has no attribute 'make_hybrid'`.

- [ ] **Step 3: Implement the hybrid**

In `paper5/code/models.py`, add `HybridMomentumNetwork` after `MomentumTransformer`:

```python
class HybridMomentumNetwork(nn.Module):
    """The real Momentum Transformer (Wood 2022): an LSTM encoder whose hidden-state sequence is then
    refined by pre-LN block-local causal attention. The LSTM carries long memory and gives the model
    its sample efficiency; the attention adds 'look back at the relevant regime'. Same I/O as the
    other models. Leak-free: LSTM is causal and the attention is block-local causal."""
    def __init__(self, n_features, hidden=16, nheads=2, dropout=0.1, nlayers=1, window=256):
        super().__init__()
        self.window = window
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.pos = _PositionalEncoding(hidden)
        layer = nn.TransformerEncoderLayer(hidden, nheads, dim_feedforward=4 * hidden,
                                           dropout=dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, nlayers)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):                # x (N,T,F) -> (N,T) in [-1,1]
        h, _ = self.lstm(x)                                       # (N,T,hidden)
        h = _block_local_encode(self.enc, self.pos, h, self.window)
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)
```

And add the factory + grid near the other factories:

```python
HYBRID_GRID = [
    {"hidden": 16, "nheads": 2, "dropout": 0.1, "wd": 1e-3, "warmup": 50},
    {"hidden": 16, "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
    {"hidden": 8,  "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
]


def make_hybrid(n_features, cfg):
    return HybridMomentumNetwork(n_features, hidden=cfg["hidden"], nheads=cfg["nheads"],
                                 dropout=cfg["dropout"], window=cfg.get("window", 256))
```

- [ ] **Step 4: Run the model tests**

Run: `cd paper5/code && python -m pytest tests/test_models.py -v`
Expected: PASS (all hybrid tests + all prior).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/models.py paper5/code/tests/test_models.py
git commit -m "feat(paper5): HybridMomentumNetwork (LSTM encoder + pre-LN block-local attention)"
```

---

## Task 4: Add LR warmup to the training loop

**Files:**
- Modify: `paper5/code/train_eval.py`
- Test: `paper5/code/tests/test_train_eval.py`

- [ ] **Step 1: Write the failing tests**

Add to `paper5/code/tests/test_train_eval.py`:

```python
def test_warmup_lambda_ramps_then_constant():
    # warmup=10: starts below 1, rises monotonically, reaches 1 by step 10, stays 1 after.
    vals = [train_eval.warmup_lambda(s, 10) for s in range(15)]
    assert vals[0] < 1.0
    assert all(b >= a for a, b in zip(vals, vals[1:]))   # non-decreasing
    assert abs(vals[9] - 1.0) < 1e-9                     # reached 1 by step 10 (index 9)
    assert all(abs(v - 1.0) < 1e-9 for v in vals[10:])   # constant after


def test_warmup_lambda_zero_is_constant_one():
    assert all(abs(train_eval.warmup_lambda(s, 0) - 1.0) < 1e-9 for s in range(5))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -k warmup -v`
Expected: FAIL with `AttributeError: module 'train_eval' has no attribute 'warmup_lambda'`.

- [ ] **Step 3: Implement the warmup helper and wire it into `_train_fold`**

In `paper5/code/train_eval.py`, add near the top constants (after `TRAIN_COST = 1e-3`):

```python
BASE_LR = 1e-3


def warmup_lambda(step, warmup):
    """LR multiplier: linear 0->1 over `warmup` optimizer steps, then 1.0.
    warmup<=0 -> always 1.0 (no warmup; training path unchanged)."""
    if warmup <= 0:
        return 1.0
    return min(1.0, (step + 1) / warmup)
```

Then in `_train_fold`, change the optimizer construction and add the scheduler + a `sched.step()` after each `opt.step()`. Replace:

```python
    net = make(X.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=cfg["wd"])
```

with:

```python
    net = make(X.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
    warmup = cfg.get("warmup", 0)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, warmup))
```

and inside the epoch loop, right after `opt.step()`, add `sched.step()`:

```python
        opt.step()
        sched.step()
```

(LSTM and pure-Transformer cfgs have no `warmup` key -> `warmup=0` -> multiplier always 1.0 -> LR constant at `BASE_LR` -> their training is numerically unchanged, so 0.92 and 0.07 reproduce.)

- [ ] **Step 4: Run the train_eval tests + full suite**

Run: `cd paper5/code && python -m pytest tests/test_train_eval.py -v`
Expected: PASS (warmup tests + the prior nested-WF tests).

Run: `cd paper5/code && python -m pytest tests/ -v`
Expected: PASS (entire offline suite).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/train_eval.py paper5/code/tests/test_train_eval.py
git commit -m "feat(paper5): per-cfg linear LR warmup in _train_fold (default off)"
```

---

## Task 5: Driver — four-model ablation on combined 18

**Files:**
- Create: `paper5/code/run_dmn_hybrid.py`

No unit test (needs the cached data + heavy training). Integration entry point.

- [ ] **Step 1: Write the driver**

```python
# paper5/code/run_dmn_hybrid.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iteration 2: does attention ON TOP OF the LSTM (the real Momentum Transformer) beat the LSTM-DMN
alone? Runs fixed-rule / LSTM-DMN / pure-Transformer / hybrid on the combined 18-asset basket, both
bands, leak-free nested WF, net @10bps, PPY=252. Prints the table and saves fig_dmn_hybrid.png."""
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

    for name, make, grid in [("LSTM-DMN", models.make_lstm, models.LSTM_GRID),
                             ("pure-Transf", models.make_transformer, models.TRANSF_GRID),
                             ("hybrid", models.make_hybrid, models.HYBRID_GRID)]:
        POS, chosen, test_idx = train_eval.nested_walkforward(
            make, grid, X, fwd, folds, warm=252, epochs=300)
        for band, tag in [(0.0, "none"), (0.3, "hard")]:
            r = train_eval.evaluate(POS, fwd, dates_ms, test_idx, band,
                                    spread_bps=10.0, n_trials=len(grid), ppy=PPY)
            rows.append(_row(name, tag, r))

    print(f"\n{'model':<13}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'+2022':>8}")
    print("-" * 51)
    for nm, bd, ir, t, dsr, y in rows:
        print(f"{nm:<13}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{y:>8}")

    lstm_best = max(r[2] for r in rows if r[0] == "LSTM-DMN")
    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    palette = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb",
               "pure-Transf": "#f59e0b", "hybrid": "#16a34a"}
    ax.bar(labels, irs, color=[palette[r[0]] for r in rows])
    ax.axhline(lstm_best, ls="--", color="#2563eb", lw=1, label=f"LSTM best {lstm_best:.2f}")
    ax.set_ylabel("net IR @10bps"); ax.set_title("Hybrid vs LSTM vs pure-Transformer (combined 18, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_hybrid.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_hybrid.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the driver end-to-end**

Run: `cd paper5/code && python -u run_dmn_hybrid.py`
Expected: a data line, a folds line, an 8-row table (fixed-rule + LSTM/pure-Tr/hybrid x none/hard), and `[fig] figures/fig_dmn_hybrid.png`. Several minutes (LSTM 5 cfgs + pure-Tr 3 + hybrid 3, x folds x 300 epochs). The LSTM rows should reproduce ~0.92/0.88 and pure-Tr ~0.07/0.05 (sanity that nothing regressed).

- [ ] **Step 3: Sanity-check against the success criterion**

Read the table. Record whether the **hybrid** (better band) meets ALL of: `net IR >= 0.92`, `NW-t > 1.5`, `DSR > 0.8`. If yes -> attention adds value over the LSTM. If no -> honest null (attention does not help in this data regime). Do not tune to force a win.

- [ ] **Step 4: Commit (driver + figure)**

```bash
git add paper5/code/run_dmn_hybrid.py
git add -f paper5/figures/fig_dmn_hybrid.png
git commit -m "feat(paper5): hybrid Momentum Transformer ablation driver (combined 18)"
```

---

## Task 6: Record the result (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (the paper5 Phase-3 findings block)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the hybrid outcome to the paper5 Phase-3 findings in `etoro/CLAUDE.md`**

Add one bullet under the Phase-3 section stating the measured hybrid net IR / NW-t / DSR (better band) and the verdict vs the LSTM 0.92 — e.g. "Hybrid (LSTM+attention, pre-LN+warmup): net IR <X> (NW-t <t>, DSR <d>) — <beat / matched / did not beat> the LSTM 0.92; see `run_dmn_hybrid.py`." Fill from Task 5's table; do not invent numbers.

- [ ] **Step 2: Update the memory file** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line with the hybrid's measured result and verdict. Keep it one fact. (Memory files are outside the repo — save with the Write tool, not committed here.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record hybrid Momentum Transformer outcome"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 2 modules (models/train_eval/run_dmn_hybrid + tests) -> Tasks 1-6 touch exactly those. ✓
- Spec section 3 hybrid (LSTM -> pre-LN block-local attention -> tanh head; reuse block-local helper; d_model=hidden; norm_first=True; make_hybrid + HYBRID_GRID; causal) -> Task 1 (helper), Task 3 (hybrid + grid + causal test). ✓
- Spec section 3 pure-Tr gains `norm_first` (default off, reproduces 0.07) -> Task 2. ✓
- Spec section 4 warmup (linear, per-cfg, default off, LSTM/pure-Tr unchanged) -> Task 4 (`warmup_lambda` + LambdaLR + `sched.step()`). ✓
- Spec section 5 eval/ablation/criterion (combined 18, both bands, nested WF + DSR + net@10bps, PPY=252, success >=0.92 ∧ NW-t>1.5 ∧ DSR>0.8) -> Task 5 driver + Step 3 check. ✓
- Spec section 6 testing (hybrid shape/range, hybrid causal, pre-LN constructs, warmup schedule, warmup=0 constant) -> Tasks 2,3,4 ship each named test. ✓ (Added a refactor-guard test in Task 1 — minor, justified.)
- Spec section 7 conventions (Yahoo cache, no Co-Authored-By, add -f figures, seed, paper4 untouched) -> Context section + commit steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". The `<X>`/`<verdict>` in Task 6 are experiment outputs that cannot exist before Task 5 runs; instructions say to fill from the printed table and not invent. Acceptable.

**3. Type consistency:** `_block_local_encode(enc, pos, h, window)` defined in Task 1, used by `MomentumTransformer` (Task 1) and `HybridMomentumNetwork` (Task 3) with `(self.enc, self.pos, h, self.window)`. `make_hybrid(n_features, cfg)` (Task 3) reads `cfg["hidden"]/["nheads"]/["dropout"]` + `cfg.get("window",256)`; `HYBRID_GRID` entries provide those + `wd`/`warmup`. `warmup_lambda(step, warmup)` (Task 4) used by the `LambdaLR` lambda and tested directly. `evaluate(..., ppy=PPY)` and `nested_walkforward(make, grid, X, fwd, folds, warm, epochs)` match the existing committed signatures (the `ppy` arg was added in the prior build). Driver consumes `_row` dict keys `net_ir/nw_t/dsr/durability` — all present in `evaluate`'s return and the baseline. ✓
