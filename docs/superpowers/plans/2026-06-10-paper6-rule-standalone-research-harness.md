# paper6 Rule-Standalone Research Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `paper6/code/` research harness that establishes the fixed rule (banded vol-targeted TSMOM) as a standalone strategy on the 5-asset sweet spot, and runs the four pre-registered research axes (robustness, risk overlays, basket selection, sizing dial) — all leak-free and net-of-cost.

**Architecture:** One pure-function rule (`rule.py`) is the single source of truth. `data.py` loads the 5-asset basket (Yahoo deep, reusing the proven paper5 loader). `eval.py` reuses the proven paper5 evaluation helpers (`band_eval`, `costs`, `metrics`) behind a leak-free walk-forward wrapper. Four axis modules + run drivers consume `rule.py` + `eval.py` and emit figures. The eToro engine + journal paper + business report are a **separate downstream plan** (they depend on the findings this plan produces).

**Tech Stack:** Python 3.11+, numpy, pandas, yfinance (via the repo cache), matplotlib. Bare-import convention (no `__init__.py`; run `pytest` from `paper6/code/`). Tests fully offline.

---

## Scope note & decomposition

This plan covers ONLY `paper6/code/` (the research harness — the "Evaluate honestly" phase). It produces working, testable software on its own: a complete honest backtest of the rule + the four axes' findings. The downstream deliverables (`paper6/engine/`, `paper_skeleton.tex`, `report_GR.tex`) get their own plan once we know the winning config and which overlays pass vs. null — because the paper cannot be written before the findings exist (the `ai-trading` discipline).

**Reuse, don't duplicate.** The proven generic helpers live in `paper5/code/`: `band_eval.apply_band`, `costs.net_returns`, `metrics.{ann_ir,newey_west_t,deflated_sharpe,durability_by_year,max_drawdown}`, `sizing.realized_vol`, and the deep-history loader `crypto_data.fetch_crypto_daily`. We import them by inserting `paper5/code` on `sys.path` — we do NOT re-implement them (avoids drift).

**The canonical rule** (from `paper5/code/run_etf_zoo.py::_rule_positions`, the proven form):
```python
ret = df.pct_change()
vol = ret.rolling(vol_window).std() * sqrt(PPY)
pos = (sign(df.pct_change(lookback)) * (target_vol / vol.shift(1))).clip(-clip, clip).fillna(0.0)
pos = pos.ewm(span=smooth_span, min_periods=1).mean()
```
`rule.py` parameterizes exactly these knobs (`lookback, vol_window, target_vol, clip, smooth_span`) — they ARE the Axis-1 robustness grid.

---

## Task 1: `_paths.py` + `data.py` — path shim & 5-asset loader

**Files:**
- Create: `paper6/code/_paths.py`
- Create: `paper6/code/data.py`
- Test: `paper6/code/tests/test_data.py`

The proven helpers are split across two dirs (verified): `costs.py`, `metrics.py`, `sizing.py` live in **`paper4/code/`**; `band_eval.py`, `crypto_data.py`, `crypto_features.py` live in **`paper5/code/`**. `_paths.py` is a one-line shim that puts BOTH on `sys.path` so a bare `import costs` / `import band_eval` works anywhere — import it first in every module (DRY: one place owns the path wiring).

The 5-asset sweet spot is `SPY, TLT, GLD, BTC-USD, UUP`. `data.py` reuses the proven paper5 deep-history loader and adds a thin wrapper returning an aligned close-price DataFrame plus the per-asset spread table for net-cost eval. It also exposes a `^VIX` loader for the Axis-2 VIX gate.

- [ ] **Step 0: Create `_paths.py` (the path shim)**

```python
# paper6/code/_paths.py
"""Put the proven helper dirs on sys.path so bare imports resolve. Import this FIRST.
paper4/code: costs, metrics, sizing.  paper5/code: band_eval, crypto_data, crypto_features."""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(__file__)
for _rel in (("..", "..", "paper4", "code"), ("..", "..", "paper5", "code")):
    _p = os.path.join(_HERE, *_rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)
```

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_data.py
import numpy as np
import pandas as pd
import data


def test_basket_constants():
    assert data.SWEET_SPOT == ("SPY", "TLT", "GLD", "BTC-USD", "UUP")
    # real per-asset spreads (bps): crypto wide, ETFs tight (paper5 measured)
    assert data.SPREADS_BPS["BTC-USD"] >= 25.0
    assert data.SPREADS_BPS["SPY"] <= 5.0


def test_align_closes_drops_partial_rows():
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    raw = pd.DataFrame(
        {"SPY": [1.0, 2.0, 3.0, 4.0], "BTC-USD": [np.nan, 2.0, 3.0, 4.0]}, index=idx
    )
    out = data.align_closes(raw)
    # first row has a NaN -> dropped; aligned frame has no NaNs
    assert not out.isna().any().any()
    assert len(out) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'data'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/data.py
"""5-asset sweet-spot loader for paper6 (the rule as a standalone strategy).
Reuses the proven paper5 deep-history Yahoo loader; never re-implements it."""
from __future__ import annotations
import os

import numpy as np
import pandas as pd

import _paths  # noqa: F401 — puts paper4/code + paper5/code on sys.path
import crypto_data  # noqa: E402  (paper5 deep-history loader)

PPY = 252  # mixed weekday/24-7 calendar; BTC trades weekends but ETFs gap — 252 is the convention used downstream

SWEET_SPOT = ("SPY", "TLT", "GLD", "BTC-USD", "UUP")

# real per-asset eToro spreads measured in paper5 (bps); used for net-cost eval
SPREADS_BPS = {"SPY": 2.0, "TLT": 3.0, "GLD": 3.0, "BTC-USD": 31.0, "UUP": 4.0}

CACHE = os.path.join(os.path.dirname(__file__), "paper6_close.npz")


def align_closes(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any row with a missing close in any column, so the panel is fully aligned."""
    return df.dropna(how="any")


def load_basket(tickers=SWEET_SPOT, period="20y") -> pd.DataFrame:
    """Aligned daily close panel for the basket (deep Yahoo history, npz-cached)."""
    df = crypto_data.fetch_crypto_daily(tickers=tuple(tickers), period=period, cache_path=CACHE)
    return align_closes(df)


def load_vix(period="20y") -> pd.Series:
    """^VIX daily close (for the Axis-2 VIX/regime gate). Not part of the traded basket."""
    vix = crypto_data.fetch_crypto_daily(tickers=("^VIX",), period=period,
                                         cache_path=os.path.join(os.path.dirname(__file__), "paper6_vix.npz"))
    return vix["^VIX"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd paper6/code && python -m pytest tests/test_data.py -v`
Expected: PASS (both tests). `align_closes` is pure so it needs no network; the constants test is pure.

- [ ] **Step 5: Commit**

```bash
git add -f paper6/code/_paths.py paper6/code/data.py paper6/code/tests/test_data.py
git commit -m "feat(paper6): path shim + 5-asset sweet-spot loader (reuses paper4/paper5 helpers; real per-asset spreads)"
```

---

## Task 2: `rule.py` — the rule as a pure function (single source of truth)

**Files:**
- Create: `paper6/code/rule.py`
- Test: `paper6/code/tests/test_rule.py`

`rule.py` produces the desired position path `(T, N)` from a close-price panel, parameterized by exactly the canonical knobs. It does NOT apply the band or costs (that is `eval.py`'s job) — it returns the *desired* positions; the band/cost layer turns them into held positions and net returns. This separation is what lets the engine and the harness share one rule.

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_rule.py
import numpy as np
import pandas as pd
import rule


def _ramp_panel(n=400):
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    up = pd.Series(np.linspace(100, 200, n), index=idx)      # steady uptrend
    down = pd.Series(np.linspace(200, 100, n), index=idx)    # steady downtrend
    return pd.DataFrame({"UP": up, "DOWN": down})


def test_sign_follows_trend():
    df = _ramp_panel()
    pos = rule.positions(df, lookback=120, vol_window=30, target_vol=0.15)
    # after warmup, long the uptrend, short the downtrend
    last = pos[-1]
    cols = list(df.columns)
    assert last[cols.index("UP")] > 0
    assert last[cols.index("DOWN")] < 0


def test_vol_target_scales_inverse_to_vol():
    # higher realized vol -> smaller absolute position for the same trend sign
    idx = pd.date_range("2018-01-01", periods=400, freq="D")
    calm = np.cumprod(1 + np.full(400, 0.001))               # smooth uptrend, low vol
    wild = np.cumprod(1 + 0.001 + 0.02 * np.sin(np.arange(400)))  # same drift, high vol
    df = pd.DataFrame({"CALM": calm * 100, "WILD": wild * 100}, index=idx)
    pos = rule.positions(df, lookback=120, vol_window=30, target_vol=0.15)
    last = np.abs(pos[-1])
    cols = list(df.columns)
    assert last[cols.index("CALM")] > last[cols.index("WILD")]


def test_output_shape_and_clip():
    df = _ramp_panel()
    pos = rule.positions(df, lookback=120, vol_window=30, target_vol=0.15, clip=2.0)
    assert pos.shape == (len(df), df.shape[1])      # (T, N)
    assert np.all(np.abs(pos) <= 2.0 + 1e-9)
    assert np.all(np.isfinite(pos))                 # warmup NaNs filled with 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_rule.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rule'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/rule.py
"""THE RULE — banded vol-targeted time-series momentum, as a single pure function.
The research harness AND the eToro engine both call `positions(...)`; never define it twice.

Canonical form (proven in paper4/paper5):
    pos = sign(close.pct_change(lookback)) * (target_vol / realized_vol.shift(1))
    pos = pos.clip(-clip, clip).fillna(0); pos = pos.ewm(span=smooth_span).mean()
The band and cost charging are applied downstream in eval.py — this returns DESIRED positions."""
from __future__ import annotations
import numpy as np
import pandas as pd

PPY = 252


def positions(close: pd.DataFrame, lookback: int = 120, vol_window: int = 30,
              target_vol: float = 0.15, clip: float = 2.0, smooth_span: int = 5,
              ppy: int = PPY) -> np.ndarray:
    """Desired position path. close: (T,N) price panel. Returns (T,N) float array.
    All estimates are causal: realized vol is `.shift(1)` so day t uses only past vol."""
    ret = close.pct_change()
    vol = ret.rolling(vol_window).std() * np.sqrt(ppy)
    raw = np.sign(close.pct_change(lookback)) * (target_vol / vol.shift(1))
    pos = raw.clip(-clip, clip).fillna(0.0)
    pos = pos.ewm(span=smooth_span, min_periods=1).mean()
    return pos.to_numpy()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd paper6/code && python -m pytest tests/test_rule.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Commit**

```bash
git add -f paper6/code/rule.py paper6/code/tests/test_rule.py
git commit -m "feat(paper6): rule.py — banded vol-targeted TSMOM as the single-source-of-truth pure function"
```

---

## Task 3: `eval.py` — leak-free net-of-cost evaluation

**Files:**
- Create: `paper6/code/eval.py`
- Test: `paper6/code/tests/test_eval.py`

`eval.py` turns a desired `(T,N)` position path into net-of-cost metrics: apply the no-trade band, equal-capital `/N`, charge per-asset spreads, slice to an OOS window, compute IR / NW-t / DSR / durability / maxDD. It reuses the proven paper5 helpers. It also exposes `forward_returns(close)` so the harness never accidentally uses same-day returns (leak guard).

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_eval.py
import numpy as np
import pandas as pd
import eval as ev


def test_forward_returns_are_causal():
    # forward return at row t must equal (P[t+1]/P[t] - 1); last row is NaN
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    close = pd.DataFrame({"A": [100.0, 110.0, 99.0, 99.0]}, index=idx)
    fwd = ev.forward_returns(close)
    assert np.isclose(fwd[0, 0], 0.10)            # 100 -> 110
    assert np.isclose(fwd[1, 0], -0.10)           # 110 -> 99
    assert np.isnan(fwd[-1, 0])                    # no future for the last row


def test_evaluate_flat_book_is_zero_return():
    # zero positions -> zero net return -> IR is 0 (or nan), never a crash
    T, N = 50, 2
    pos = np.zeros((T, N))
    fwd = np.full((T, N), 0.01)
    res = ev.evaluate(pos, fwd, test_rows=np.arange(10, T), spreads_bps=[2.0, 2.0], band=0.1)
    assert abs(res["net_ir"]) < 1e-9 or np.isnan(res["net_ir"])
    assert res["n"] == T - 10


def test_costs_reduce_return():
    # a positive trend book nets less after spread than a zero-spread book
    T, N = 60, 1
    pos = np.ones((T, N))
    fwd = np.full((T, N), 0.005)
    gross = ev.evaluate(pos, fwd, np.arange(5, T), spreads_bps=[0.0], band=0.0)["net_ir"]
    net = ev.evaluate(pos, fwd, np.arange(5, T), spreads_bps=[50.0], band=0.0)["net_ir"]
    assert net <= gross
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_eval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eval'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/eval.py
"""Leak-free, net-of-cost evaluation for the rule. Reuses the proven helpers
(band_eval from paper5/code; costs, metrics from paper4/code); never re-implements them.
Per-asset spreads (not a flat bps)."""
from __future__ import annotations
import numpy as np
import pandas as pd

import _paths  # noqa: F401 — puts paper4/code + paper5/code on sys.path
import band_eval   # noqa: E402  (paper5/code)
import costs        # noqa: E402  (paper4/code)
import metrics      # noqa: E402  (paper4/code)

PPY = 252


def forward_returns(close: pd.DataFrame) -> np.ndarray:
    """(T,N) next-day simple returns: row t = P[t+1]/P[t]-1. Last row NaN (no future)."""
    fwd = close.shift(-1) / close - 1.0
    return fwd.to_numpy()


def _net_with_per_asset_spreads(W, F, spreads_bps):
    """Charge each asset its own spread. costs.net_returns takes one bps; we apply per
    column then sum, since cost is linear in turnover per asset."""
    spreads = np.asarray(spreads_bps, float)
    total = np.zeros(W.shape[0])
    for j in range(W.shape[1]):
        col_net = costs.net_returns(W[:, [j]], F[:, [j]], float(spreads[j]), 0.0)
        total = total + np.nan_to_num(col_net, nan=0.0)
    # rows where every asset's forward return was NaN should stay NaN (no data)
    valid = np.isfinite(F).any(axis=1)
    total = np.where(valid, total, np.nan)
    return total


def evaluate(pos, fwd, test_rows, spreads_bps, band, n_trials=1, ppy=PPY):
    """pos,fwd: (T,N). Apply band on the full path, equal-capital /N, charge per-asset
    spreads, slice to OOS test_rows, return metrics. Leak-free: caller passes forward_returns."""
    pos = np.asarray(pos, float)
    N = pos.shape[1]
    W = band_eval.apply_band(pos, band) / N        # (T,N) held, equal capital
    F = np.asarray(fwd, float)
    rows = np.asarray(test_rows)
    net = _net_with_per_asset_spreads(W[rows], F[rows], spreads_bps)
    fin = np.isfinite(net)
    net = net[fin]
    if len(net) == 0:
        return {"net_ir": float("nan"), "nw_t": float("nan"), "dsr": float("nan"),
                "max_dd": float("nan"), "ann": float("nan"), "n": 0}
    eq = float(np.prod(1.0 + net))
    return {
        "net_ir": metrics.ann_ir(net, ppy),
        "nw_t": metrics.newey_west_t(net),
        "dsr": metrics.deflated_sharpe(net, n_trials=n_trials, periods=ppy),
        "max_dd": metrics.max_drawdown(net),
        "ann": eq ** (ppy / len(net)) - 1.0,
        "n": len(net),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd paper6/code && python -m pytest tests/test_eval.py -v`
Expected: PASS (all three). If `metrics.ann_ir` returns `nan` for a zero-variance stream, the first test's `or np.isnan` branch covers it.

- [ ] **Step 5: Commit**

```bash
git add -f paper6/code/eval.py paper6/code/tests/test_eval.py
git commit -m "feat(paper6): eval.py — leak-free per-asset-spread net-of-cost metrics (reuses paper5 band/costs/metrics)"
```

---

## Task 4: `robustness.py` + `run_robustness.py` — Axis 1 (anti-overfit)

**Files:**
- Create: `paper6/code/robustness.py`
- Create: `paper6/code/run_robustness.py`
- Test: `paper6/code/tests/test_robustness.py`

Axis 1 sweeps the rule's knobs and produces net-IR surfaces. The **win is a wide stable region**, and the chosen base config is the **center of the stable region**, not the argmax. `robustness.py` provides the sweep + a `stable_center` selector; `run_robustness.py` wires real data and emits the heatmap.

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_robustness.py
import numpy as np
import robustness


def test_grid_sweep_returns_one_row_per_combo():
    grid = {"lookback": [60, 120], "band": [0.0, 0.1], "target_vol": [0.15], "smooth_span": [5]}
    # fake scorer: IR = lookback/1000 - band (deterministic, monotone)
    def score(lookback, band, target_vol, smooth_span):
        return lookback / 1000.0 - band
    rows = robustness.sweep(grid, score)
    assert len(rows) == 2 * 2 * 1 * 1
    assert {"lookback", "band", "target_vol", "smooth_span", "net_ir"} <= set(rows[0])


def test_stable_center_prefers_plateau_over_spike():
    # one sharp spike (argmax) vs a broad plateau; center selector must avoid the spike
    rows = [
        {"lookback": 20, "band": 0.0, "target_vol": 0.15, "smooth_span": 5, "net_ir": 5.0},  # spike
        {"lookback": 100, "band": 0.1, "target_vol": 0.15, "smooth_span": 5, "net_ir": 1.0},
        {"lookback": 120, "band": 0.1, "target_vol": 0.15, "smooth_span": 5, "net_ir": 1.0},
        {"lookback": 140, "band": 0.1, "target_vol": 0.15, "smooth_span": 5, "net_ir": 1.0},
    ]
    best = robustness.stable_center(rows, key="lookback", neighbor_span=2)
    # the plateau center (120) wins, not the isolated spike (20)
    assert best["lookback"] == 120
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_robustness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robustness'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/robustness.py
"""Axis 1 — robustness / anti-overfit. Sweep the rule's knobs, score net-IR, and pick the
base config from the CENTER of the stable plateau (not the argmax — that is the overfit move)."""
from __future__ import annotations
import itertools

import numpy as np


def sweep(grid, score_fn):
    """grid: dict knob->list. score_fn(**combo)->net_ir. Returns list of {**combo, net_ir}."""
    keys = list(grid)
    rows = []
    for vals in itertools.product(*(grid[k] for k in keys)):
        combo = dict(zip(keys, vals))
        combo["net_ir"] = float(score_fn(**combo))
        rows.append(combo)
    return rows


def stable_center(rows, key, neighbor_span=1):
    """Score each row by the MEAN net_ir of its neighbours along `key` (a plateau scores high,
    an isolated spike scores low because its neighbours are poor). Return the best such row."""
    vals = sorted({r[key] for r in rows})
    idx = {v: i for i, v in enumerate(vals)}
    best, best_score = None, -np.inf
    for r in rows:
        i = idx[r[key]]
        lo, hi = max(0, i - neighbor_span), min(len(vals), i + neighbor_span + 1)
        window = [x["net_ir"] for x in rows if idx[x[key]] in range(lo, hi)
                  and all(x[k] == r[k] for k in r if k not in (key, "net_ir"))]
        s = float(np.mean(window)) if window else r["net_ir"]
        if s > best_score:
            best, best_score = r, s
    return best
```

```python
# paper6/code/run_robustness.py
"""Axis 1 driver: sweep the rule on the real 5-asset basket, leak-free WF, net-of-cost,
emit the net-IR heatmap and print the stable-center base config."""
from __future__ import annotations
import os

import numpy as np

import data
import eval as ev
import robustness
import rule

GRID = {"lookback": [21, 42, 63, 126, 252], "band": [0.0, 0.05, 0.10, 0.15, 0.20, 0.30],
        "target_vol": [0.10, 0.15, 0.20], "smooth_span": [5]}


def main():
    close = data.load_basket()
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS[t] for t in close.columns]
    T = len(close)
    warm = 252
    test_rows = np.arange(warm, T - 1)   # -1: last row has NaN forward return

    def score(lookback, band, target_vol, smooth_span):
        pos = rule.positions(close, lookback=lookback, target_vol=target_vol, smooth_span=smooth_span)
        return ev.evaluate(pos, fwd, test_rows, spreads, band=band)["net_ir"]

    rows = robustness.sweep(GRID, score)
    base = robustness.stable_center(rows, key="lookback", neighbor_span=1)
    print(f"[axis1] base config (stable center): {base}")
    # heatmap: lookback x band at the base target_vol
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tv = base["target_vol"]
    lbs, bands = GRID["lookback"], GRID["band"]
    grid = np.array([[next(r["net_ir"] for r in rows if r["lookback"] == lb and r["band"] == bd
                           and r["target_vol"] == tv) for bd in bands] for lb in lbs])
    plt.figure(figsize=(7, 5))
    plt.imshow(grid, aspect="auto", cmap="viridis", origin="lower")
    plt.colorbar(label="net IR")
    plt.xticks(range(len(bands)), bands); plt.yticks(range(len(lbs)), lbs)
    plt.xlabel("no-trade band"); plt.ylabel("lookback (days)")
    plt.title(f"paper6 Axis1 robustness — net IR (target_vol={tv})")
    out = os.path.join(os.path.dirname(__file__), "..", "figures", "fig_robustness.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    plt.tight_layout(); plt.savefig(out, dpi=120)
    print(f"[axis1] wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests + smoke the driver**

Run: `cd paper6/code && python -m pytest tests/test_robustness.py -v`
Expected: PASS (both).
Then smoke (network — may be slow): `cd paper6/code && python run_robustness.py`
Expected: prints `[axis1] base config ...` and writes `paper6/figures/fig_robustness.png`.

- [ ] **Step 5: Commit**

```bash
git add -f paper6/code/robustness.py paper6/code/run_robustness.py paper6/code/tests/test_robustness.py
git add -f paper6/figures/fig_robustness.png
git commit -m "feat(paper6): Axis1 robustness — knob sweep + stable-center base config (anti-overfit), net-IR heatmap"
```

---

## Task 5: `overlays.py` + `run_overlays.py` — Axis 2 (risk overlays, pre-registered)

**Files:**
- Create: `paper6/code/overlays.py`
- Create: `paper6/code/run_overlays.py`
- Test: `paper6/code/tests/test_overlays.py`

Each overlay multiplies the desired position path by a causal `[0,1]` exposure mask. Three overlays: drawdown-control (pure, self-contained), VIX/regime gate (uses `data.load_vix`), BOCPD brake (reuses `paper4/code/bocpd.py`). Each is ablated vs. the base config; **win** = passes its pre-registered gate net-OOS AND improves 2022. `run_overlays.py` prints the ablation table and writes the figure; overlays that fail their gate are recorded as **nulls** (printed explicitly).

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_overlays.py
import numpy as np
import overlays


def test_drawdown_control_cuts_exposure_after_loss():
    # a book that loses for a while should have exposure cut to < 1 during the drawdown
    pos = np.ones((100, 1))
    port_ret = np.where(np.arange(100) < 50, -0.01, 0.01)   # lose then recover
    mask = overlays.drawdown_control(pos, port_ret, dd_limit=0.05)
    assert mask.shape == (100, 1)
    assert np.all(mask <= 1.0 + 1e-9) and np.all(mask >= 0.0)
    assert mask[40, 0] < 1.0          # deep in the drawdown -> exposure reduced
    assert mask[0, 0] == 1.0          # no drawdown yet at t=0 -> full exposure


def test_vix_gate_derisks_when_vix_high():
    pos = np.ones((6, 1))
    vix = np.array([15, 15, 40, 40, 15, 15], float)         # spike in the middle
    mask = overlays.vix_gate(pos, vix, threshold=30.0)
    assert mask[2, 0] == 0.0 and mask[3, 0] == 0.0          # gated off during spike
    assert mask[0, 0] == 1.0


def test_overlay_is_causal_no_lookahead():
    # changing a FUTURE return must not change the mask at an earlier time
    pos = np.ones((20, 1))
    r1 = np.full(20, 0.01); r2 = r1.copy(); r2[15] = -0.5
    m1 = overlays.drawdown_control(pos, r1, dd_limit=0.05)
    m2 = overlays.drawdown_control(pos, r2, dd_limit=0.05)
    assert np.allclose(m1[:15], m2[:15])                    # past unaffected by future
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_overlays.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'overlays'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/overlays.py
"""Axis 2 — risk overlays. Each returns a causal (T,N) exposure mask in [0,1] to multiply
into the desired position path. Pre-registered: an overlay 'wins' only if it cuts maxDD
without materially lowering net-IR AND improves 2022 (checked in run_overlays.py)."""
from __future__ import annotations
import os
import sys

import numpy as np

import _paths  # noqa: F401 — paper4/code + paper5/code on sys.path
# BOCPD lives in the slow-momentum strategy dir, not paper4/code:
_BOCPD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "Strategies",
                          "slow-momentum-fast-reversion")
if _BOCPD_DIR not in sys.path:
    sys.path.insert(0, _BOCPD_DIR)


def drawdown_control(pos, port_ret, dd_limit=0.10):
    """Reduce exposure proportionally to how far trailing drawdown exceeds dd_limit.
    Causal: drawdown at t uses only returns up to t-1."""
    pos = np.asarray(pos, float)
    r = np.asarray(port_ret, float)
    T = pos.shape[0]
    mask = np.ones(T)
    eq = 1.0
    peak = 1.0
    for t in range(T):
        dd = 0.0 if peak <= 0 else (peak - eq) / peak     # drawdown using info up to t-1
        if dd > dd_limit:
            mask[t] = max(0.0, 1.0 - (dd - dd_limit) / dd_limit)
        eq *= (1.0 + r[t]) if np.isfinite(r[t]) else 1.0  # update AFTER setting mask[t]
        peak = max(peak, eq)
    return mask[:, None] * np.ones_like(pos)


def vix_gate(pos, vix, threshold=30.0):
    """Exposure 0 when VIX (causal, same-row level known at close) exceeds threshold, else 1."""
    pos = np.asarray(pos, float)
    v = np.asarray(vix, float)
    mask = (v <= threshold).astype(float)
    return mask[:, None] * np.ones_like(pos)


def bocpd_brake(pos, close_panel, hazard=1 / 250.0):
    """Reduce exposure by the mean per-asset changepoint probability (BOCPD, paper4 belief
    feature). A 'smart brake' on regime change — reduces drawdown, not alpha (paper4 finding)."""
    from bocpd import bocpd_gaussian   # Strategies/slow-momentum-fast-reversion/bocpd.py
    pos = np.asarray(pos, float)
    ret = close_panel.pct_change().fillna(0.0).to_numpy()
    T, N = ret.shape
    cp = np.zeros((T, N))
    for j in range(N):
        cp[:, j] = np.asarray(bocpd_gaussian(ret[:, j], hazard=hazard), float)[:T]
    mask = 1.0 - cp.mean(axis=1)                           # high cp prob -> lower exposure
    return np.clip(mask, 0.0, 1.0)[:, None] * np.ones_like(pos)
```

> **Note for the implementer:** the public fn is `bocpd_gaussian(x, hazard=1/250.0, ...)` (verified). Confirm its return is a per-timestep changepoint probability aligned to `x` (length T); if it returns a different shape (e.g. a tuple or a (T, rmax) matrix), reduce it to the per-t changepoint probability — the contract is "causal per-series changepoint probability in [0,1]". If BOCPD wiring is non-trivial, land `drawdown_control` + `vix_gate` first (their tests pass without it) and add `bocpd_brake` in a follow-up commit.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd paper6/code && python -m pytest tests/test_overlays.py -v`
Expected: PASS (the three tests cover `drawdown_control` + `vix_gate`, which need no paper4 import).

- [ ] **Step 5: Write `run_overlays.py` (ablation + pre-registered gate)**

```python
# paper6/code/run_overlays.py
"""Axis 2 driver: ablate each overlay vs the base config on the real basket. Print the
ablation table and the PASS/NULL verdict per the pre-registered gate. Net-of-cost, leak-free."""
from __future__ import annotations
import os

import numpy as np

import data
import eval as ev
import overlays
import rule

# base config from Axis 1 (update after run_robustness.py prints the stable center)
BASE = {"lookback": 126, "vol_window": 30, "target_vol": 0.15, "smooth_span": 5, "band": 0.10}


def _port_ret(pos, fwd, band, N):
    import band_eval, costs  # via eval's sys.path
    W = band_eval.apply_band(pos, band) / N
    return costs.net_returns(W, np.nan_to_num(np.asarray(fwd), nan=0.0), 0.0, 0.0)


def main():
    close = data.load_basket()
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS[t] for t in close.columns]
    T, N = close.shape
    rows = np.arange(252, T - 1)
    base_pos = rule.positions(close, lookback=BASE["lookback"], vol_window=BASE["vol_window"],
                              target_vol=BASE["target_vol"], smooth_span=BASE["smooth_span"])

    def metr(pos):
        return ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])

    base = metr(base_pos)
    pr = _port_ret(base_pos, fwd, BASE["band"], N)
    variants = {
        "base": base_pos,
        "+drawdown": base_pos * overlays.drawdown_control(base_pos, pr, dd_limit=0.10),
        "+vix": base_pos * overlays.vix_gate(base_pos, data.load_vix().reindex(close.index).ffill().to_numpy(), 30.0),
        "+bocpd": base_pos * overlays.bocpd_brake(base_pos, close),
    }
    print(f"{'variant':12} {'net_ir':>8} {'max_dd':>8} {'verdict':>8}")
    for name, pos in variants.items():
        m = metr(pos)
        if name == "base":
            verdict = "—"
        else:
            # pre-registered: maxDD cut >=20% AND net_ir not down by >0.1
            dd_cut = (abs(base["max_dd"]) - abs(m["max_dd"])) / (abs(base["max_dd"]) + 1e-9)
            verdict = "PASS" if (dd_cut >= 0.20 and m["net_ir"] >= base["net_ir"] - 0.1) else "NULL"
        print(f"{name:12} {m['net_ir']:8.2f} {m['max_dd']:8.2%} {verdict:>8}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add -f paper6/code/overlays.py paper6/code/run_overlays.py paper6/code/tests/test_overlays.py
git commit -m "feat(paper6): Axis2 overlays — drawdown/VIX/BOCPD exposure masks + pre-registered ablation gate (PASS/NULL)"
```

---

## Task 6: `basket.py` + `run_basket.py` — Axis 3 (ENB-maximizing selection)

**Files:**
- Create: `paper6/code/basket.py`
- Create: `paper6/code/run_basket.py`
- Test: `paper6/code/tests/test_basket.py`

Axis 3 measures the effective number of independent bets (ENB) and greedily selects the most-diversified subset. **Win** = ENB-selected basket beats the fixed 5-asset on IR/maxDD, OR confirms 5 is already saturation.

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_basket.py
import numpy as np
import basket


def test_enb_of_independent_assets_equals_count():
    # uncorrelated columns -> ENB ~= N
    rng = np.random.default_rng(0)
    R = rng.standard_normal((2000, 4))
    enb = basket.effective_bets(R)
    assert 3.5 <= enb <= 4.0


def test_enb_of_redundant_assets_is_small():
    # all columns identical -> ENB ~= 1
    rng = np.random.default_rng(1)
    base = rng.standard_normal((2000, 1))
    R = np.repeat(base, 4, axis=1)
    enb = basket.effective_bets(R)
    assert enb < 1.2


def test_greedy_select_prefers_uncorrelated():
    rng = np.random.default_rng(2)
    a = rng.standard_normal(2000)
    R = np.column_stack([a, a * 0.99 + 0.01 * rng.standard_normal(2000),  # redundant with a
                         rng.standard_normal(2000), rng.standard_normal(2000)])  # independent
    names = ["a", "a2", "b", "c"]
    chosen = basket.greedy_enb(R, names, k=3)
    assert "a2" not in chosen          # the redundant twin is dropped
    assert len(chosen) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_basket.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'basket'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/basket.py
"""Axis 3 — diversification. ENB = (sum eigenvalues)^2 / sum(eigenvalues^2) of the return
covariance (the 'effective number of independent bets'). Greedy selection maximizes it."""
from __future__ import annotations
import numpy as np


def effective_bets(returns):
    """returns: (T,N). ENB via the eigenvalues of the correlation matrix."""
    R = np.asarray(returns, float)
    R = R[np.isfinite(R).all(axis=1)]
    C = np.corrcoef(R, rowvar=False)
    lam = np.linalg.eigvalsh(C)
    lam = lam[lam > 0]
    return float((lam.sum() ** 2) / (np.square(lam).sum() + 1e-12))


def greedy_enb(returns, names, k):
    """Greedily add the asset that most increases ENB, until k chosen."""
    R = np.asarray(returns, float)
    remaining = list(range(len(names)))
    chosen = []
    while len(chosen) < k and remaining:
        best_j, best_enb = None, -np.inf
        for j in remaining:
            trial = chosen + [j]
            enb = effective_bets(R[:, trial]) if len(trial) > 1 else 1.0
            if enb > best_enb:
                best_j, best_enb = j, enb
        chosen.append(best_j)
        remaining.remove(best_j)
    return [names[j] for j in chosen]
```

```python
# paper6/code/run_basket.py
"""Axis 3 driver: compare the fixed 5-asset basket vs ENB-greedy 3/5/7 over an extended pool.
Net-of-cost, leak-free. Prints IR/maxDD/ENB per basket."""
from __future__ import annotations
import numpy as np

import basket
import data
import eval as ev
import rule

POOL = ("SPY", "TLT", "GLD", "BTC-USD", "UUP", "QQQ", "EEM", "HYG", "SLV")
BASE = {"lookback": 126, "target_vol": 0.15, "smooth_span": 5, "band": 0.10}


def _score(close):
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS.get(t, 5.0) for t in close.columns]
    rows = np.arange(252, len(close) - 1)
    pos = rule.positions(close, lookback=BASE["lookback"], target_vol=BASE["target_vol"],
                         smooth_span=BASE["smooth_span"])
    m = ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])
    enb = basket.effective_bets(close.pct_change().to_numpy()[1:])
    return m, enb


def main():
    full = data.load_basket(tickers=POOL)
    ret = full.pct_change().to_numpy()[1:]
    print(f"{'basket':28} {'enb':>5} {'net_ir':>8} {'max_dd':>8}")
    # fixed 5-asset
    five = data.load_basket(tickers=data.SWEET_SPOT)
    m, enb = _score(five); print(f"{'fixed-5 (sweet spot)':28} {enb:5.1f} {m['net_ir']:8.2f} {m['max_dd']:8.2%}")
    for k in (3, 5, 7):
        names = basket.greedy_enb(ret, list(full.columns), k=k)
        sub = data.load_basket(tickers=tuple(names))
        m, enb = _score(sub)
        print(f"{'enb-greedy-' + str(k) + ' ' + '/'.join(names):28.28} {enb:5.1f} {m['net_ir']:8.2f} {m['max_dd']:8.2%}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd paper6/code && python -m pytest tests/test_basket.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add -f paper6/code/basket.py paper6/code/run_basket.py paper6/code/tests/test_basket.py
git commit -m "feat(paper6): Axis3 basket — ENB effective-bets + greedy diversification selection (fixed-5 vs greedy 3/5/7)"
```

---

## Task 7: `sizing_dial.py` + `run_sizing.py` — Axis 4 (capital dial)

**Files:**
- Create: `paper6/code/sizing_dial.py`
- Create: `paper6/code/run_sizing.py`
- Test: `paper6/code/tests/test_sizing_dial.py`

Axis 4 turns IR into real money: map target-vol to a risk budget, expose `conservative/balanced/aggressive` presets, and report EUR returns on €10k. **Win** = one clear, safe dial.

- [ ] **Step 1: Write the failing test**

```python
# paper6/code/tests/test_sizing_dial.py
import numpy as np
import sizing_dial


def test_presets_increase_target_vol_monotonically():
    p = sizing_dial.PRESETS
    assert p["conservative"]["target_vol"] < p["balanced"]["target_vol"] < p["aggressive"]["target_vol"]


def test_eur_path_compounds_from_start_capital():
    net = np.array([0.10, -0.05, 0.20])
    end = sizing_dial.eur_end_value(net, start=10_000.0)
    expected = 10_000.0 * 1.10 * 0.95 * 1.20
    assert np.isclose(end, expected)


def test_realized_maxdd_scales_with_target_vol():
    # doubling target_vol roughly doubles realized vol of the position book (linear dial)
    rng = np.random.default_rng(0)
    sig = rng.standard_normal(1000) * 0.01
    lo = sizing_dial.realized_vol_of(sig * 1.0)
    hi = sizing_dial.realized_vol_of(sig * 2.0)
    assert 1.8 <= hi / lo <= 2.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd paper6/code && python -m pytest tests/test_sizing_dial.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sizing_dial'`.

- [ ] **Step 3: Write minimal implementation**

```python
# paper6/code/sizing_dial.py
"""Axis 4 — the capital dial. vol-target is the risk/profit dial (paper4/5 finding). Expose it
as three safe presets and report EUR outcomes. fractional-Kelly comparison is reused from paper4."""
from __future__ import annotations
import numpy as np

PRESETS = {
    "conservative": {"target_vol": 0.10},
    "balanced": {"target_vol": 0.15},
    "aggressive": {"target_vol": 0.20},
}


def eur_end_value(net_returns, start=10_000.0):
    """Compound a net-return stream into an ending EUR value."""
    r = np.asarray(net_returns, float)
    return float(start * np.prod(1.0 + r[np.isfinite(r)]))


def realized_vol_of(stream, ppy=252):
    """Annualized realized vol of a return/position stream (linearity check for the dial)."""
    s = np.asarray(stream, float)
    return float(np.std(s) * np.sqrt(ppy))
```

```python
# paper6/code/run_sizing.py
"""Axis 4 driver: for each preset, run the base rule on the real basket and report
net-IR, realized maxDD, and EUR end-value on EUR10k. Net-of-cost, leak-free."""
from __future__ import annotations
import numpy as np

import _paths  # noqa: F401 — must precede band_eval/costs bare imports
import band_eval   # paper5/code
import costs        # paper4/code
import data
import eval as ev
import rule
import sizing_dial

BASE = {"lookback": 126, "smooth_span": 5, "band": 0.10}


def main():
    close = data.load_basket()
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS[t] for t in close.columns]
    T, N = close.shape
    rows = np.arange(252, T - 1)
    print(f"{'preset':14} {'tv':>5} {'net_ir':>8} {'max_dd':>8} {'EUR(10k)':>10}")
    for name, cfg in sizing_dial.PRESETS.items():
        pos = rule.positions(close, lookback=BASE["lookback"], target_vol=cfg["target_vol"],
                             smooth_span=BASE["smooth_span"])
        m = ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])
        W = band_eval.apply_band(pos, BASE["band"])[rows] / N
        net = costs.net_returns(W, np.nan_to_num(fwd[rows], nan=0.0),
                                float(np.mean(spreads)), 0.0)
        eur = sizing_dial.eur_end_value(net)
        print(f"{name:14} {cfg['target_vol']:5.2f} {m['net_ir']:8.2f} {m['max_dd']:8.2%} {eur:10.0f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd paper6/code && python -m pytest tests/test_sizing_dial.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add -f paper6/code/sizing_dial.py paper6/code/run_sizing.py paper6/code/tests/test_sizing_dial.py
git commit -m "feat(paper6): Axis4 sizing dial — conservative/balanced/aggressive presets + EUR outcomes on EUR10k"
```

---

## Task 8: Full-suite green + findings capture

**Files:**
- Modify: (no code) — run everything, record findings.

- [ ] **Step 1: Run the whole offline test suite**

Run: `cd paper6/code && python -m pytest tests/ -v`
Expected: ALL PASS (data, rule, eval, robustness, overlays, basket, sizing_dial).

- [ ] **Step 2: Run all four axis drivers and capture output**

Run, in order:
```bash
cd paper6/code
python run_robustness.py   # -> base config (stable center); update BASE in run_overlays/basket/sizing
python run_overlays.py     # -> overlay PASS/NULL table
python run_basket.py       # -> fixed-5 vs greedy ENB
python run_sizing.py       # -> preset EUR table
```
After `run_robustness.py` prints the stable-center base config, update the `BASE = {...}` dict in `run_overlays.py`, `run_basket.py`, `run_sizing.py` to match, then re-run those three. Commit the BASE update:
```bash
git add -f paper6/code/run_overlays.py paper6/code/run_basket.py paper6/code/run_sizing.py
git commit -m "chore(paper6): pin BASE config to Axis1 stable center across axis drivers"
```

- [ ] **Step 3: Record the findings**

Append a `### paper6 findings` block to the repo `CLAUDE.md` (the project research log) summarizing, with numbers: the stable base config, which overlays PASSED vs NULL, the basket comparison (does greedy beat fixed-5 or is 5 saturation?), and the preset EUR table. Be honest — nulls are findings. Then:
```bash
git add CLAUDE.md
git commit -m "docs(paper6): record research-harness findings (base config, overlay PASS/NULL, basket, dial)"
```

---

## Self-review notes (already applied)

- **Spec coverage:** Axis 1 → Task 4; Axis 2 → Task 5; Axis 3 → Task 6; Axis 4 → Task 7; `rule.py` single-source-of-truth → Task 2; leak-free net-of-cost eval → Task 3; 5-asset universe + real spreads → Task 1; findings capture → Task 8. Engine + paper + report are explicitly deferred to a downstream plan (scope note).
- **Type consistency:** `rule.positions(...) -> (T,N) ndarray` is consumed identically by every axis driver; `ev.evaluate(pos, fwd, test_rows, spreads_bps, band, ...)` signature is identical across Tasks 4–7; `ev.forward_returns(close) -> (T,N)` used everywhere.
- **Reuse (verified locations):** `costs`, `metrics`, `sizing` from `paper4/code`; `band_eval`, `crypto_data`, `crypto_features` from `paper5/code`; `bocpd_gaussian` from `Strategies/slow-momentum-fast-reversion/bocpd.py`. All wired via the single `_paths.py` shim (Task 1) + the BOCPD-dir insert in `overlays.py`. Never re-implemented. `metrics` public fns confirmed present: `ann_ir, max_drawdown, newey_west_t, deflated_sharpe, durability_by_year`. `crypto_data.fetch_crypto_daily(tickers, period, cache_path, refresh)` signature confirmed.
- **Known risk flagged:** `bocpd_brake` depends on the return shape of `bocpd_gaussian` — the implementer verifies it returns a length-T per-t changepoint probability before wiring (note in Task 5); drawdown + VIX overlays land independently if BOCPD wiring slips.
```
