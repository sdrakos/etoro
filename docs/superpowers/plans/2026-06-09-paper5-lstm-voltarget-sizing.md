# LSTM + Volatility-Target Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the LSTM the rule's proven volatility-target sizing (serving-time, no retraining), on the diversified 5-asset basket, and sweep the vol-target dial to raise the LSTM's risk-adjusted profit — comparing raw-LSTM / sized-LSTM / rule on Yahoo-deep, then validating the best on real eToro prices.

**Architecture:** A small pure sizing wrapper `size_positions` (offline-tested) re-scales the LSTM's `tanh` positions by inverse vol. A Yahoo driver runs the LSTM walk-forward once and evaluates raw vs sized (dial sweep) vs rule. The best dial config is then validated on real eToro prices via the existing read-only backtest helpers. The torch training functions and paper4 are untouched.

**Tech Stack:** Python 3.11+, NumPy/pandas, PyTorch (LSTM), scikit not needed, matplotlib, the eToro demo client (validation only). Tests: pytest, offline.

---

## Context for the implementer (read once)

cwd `etoro/`. `paper5/code/` is bare-import (no `__init__.py`; tests in `paper5/code/tests/`, run `python -m pytest` from `paper5/code/`). Do NOT modify `paper4/` or the torch training functions in `train_eval.py` (only CALL them). Commits: clean, NO `Co-Authored-By`. Figures: `git add -f`.

**Reuse:** `combined_data.fetch_combined_daily()` -> real (T,18) Yahoo close DataFrame (columns include `SPY,TLT,GLD,BTC-USD,UUP`). `crypto_features.build(close_df) -> (X (N,T,10), fwd (N,T), dates_ms)`. `train_eval.{make_folds, nested_walkforward(make, grid, X, fwd, folds, warm, epochs)->(POS, chosen, test_idx), evaluate}`. `models.make_lstm`/`LSTM_GRID`. `band_eval.apply_band(pos_TN, band)`. `paper4/code/costs.net_returns(W (T,N), fwd (T,N), spread_bps, short_fin)`. `metrics.{ann_ir, newey_west_t, deflated_sharpe, max_drawdown}`. For eToro validation: `paper5/engine/etoro_gbt_backtest.{panel_to_xy, _spread_vec, _rule_positions, net_per_asset}` + the resolve/fetch pattern.

**The 5-asset sweet spot:** `["SPY", "TLT", "GLD", "BTC-USD", "UUP"]`. PPY = 252 (weekday calendar from `combined_data`).

---

## File Structure

- `paper5/code/lstm_sizing.py` — **create**: `size_positions(POS, vol, target_vol, clip, ewm_span)`.
- `paper5/code/run_lstm_sizing.py` — **create**: Yahoo 5-asset sweep (raw / sized dials / rule).
- `paper5/code/tests/test_lstm_sizing.py` — **create**: wrapper unit tests.
- `paper5/engine/etoro_lstm_sized.py` — **create**: eToro real-price validation of the best dial.

---

## Task L1: The sizing wrapper

**Files:**
- Create: `paper5/code/lstm_sizing.py`
- Create: `paper5/code/tests/test_lstm_sizing.py`

- [ ] **Step 1: Write the failing tests**

```python
# paper5/code/tests/test_lstm_sizing.py
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lstm_sizing as ls


def test_zero_target_vol_zero_position():
    POS = np.full((3, 10), 0.5); vol = np.full((3, 10), 0.2)
    assert np.allclose(ls.size_positions(POS, vol, target_vol=0.0), 0.0)


def test_inverse_vol_halves_when_vol_doubles():
    POS = np.full((2, 20), 0.5)
    a = ls.size_positions(POS, np.full((2, 20), 0.2), target_vol=0.15, clip=10.0, ewm_span=1)
    b = ls.size_positions(POS, np.full((2, 20), 0.4), target_vol=0.15, clip=10.0, ewm_span=1)
    assert np.allclose(b, a / 2.0, atol=1e-9)


def test_clip_caps_at_two_and_shape():
    POS = np.ones((2, 5)); vol = np.full((2, 5), 0.01)
    out = ls.size_positions(POS, vol, target_vol=0.15, clip=2.0, ewm_span=1)
    assert out.shape == (2, 5)
    assert np.all(np.abs(out) <= 2.0 + 1e-9) and np.isfinite(out).all()


def test_smoothing_softens_a_step():
    POS = np.array([[0.0, 0, 0, 1.0, 1, 1, 1, 1]]); vol = np.full((1, 8), 1.0)
    out = ls.size_positions(POS, vol, target_vol=1.0, clip=10.0, ewm_span=5)
    assert 0.0 < out[0, 3] < 1.0          # EWM softens the jump at the step
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/code && python -m pytest tests/test_lstm_sizing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lstm_sizing'`.

- [ ] **Step 3: Implement**

```python
# paper5/code/lstm_sizing.py
"""Volatility-target sizing for the LSTM signal (serving-time, no retraining). The LSTM emits a
tanh position in [-1,1] (direction + conviction); we re-scale it by inverse vol like the fixed rule:
position = clip(LSTM * target_vol/vol, +/-clip), then per-asset EWM. The no-trade band is applied
downstream by evaluate(). target_vol is the profit/risk dial."""
from __future__ import annotations
import numpy as np
import pandas as pd


def size_positions(POS, vol, target_vol=0.15, clip=2.0, ewm_span=5):
    """POS (N,T) raw LSTM tanh positions; vol (N,T) causal annualized realized vol.
    Returns vol-targeted positions (N,T)."""
    sized = np.clip(np.asarray(POS, float) * (target_vol / np.maximum(np.asarray(vol, float), 1e-6)),
                    -clip, clip)
    return pd.DataFrame(sized.T).ewm(span=ewm_span, min_periods=1).mean().to_numpy().T
```

- [ ] **Step 4: Run the tests**

Run: `cd paper5/code && python -m pytest tests/test_lstm_sizing.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add paper5/code/lstm_sizing.py paper5/code/tests/test_lstm_sizing.py
git commit -m "feat(paper5): vol-target sizing wrapper for the LSTM signal (serving-time)"
```

---

## Task L2: Yahoo 5-asset sweep driver

**Files:**
- Create: `paper5/code/run_lstm_sizing.py`

No unit test (heavy LSTM training). Integration entry point.

- [ ] **Step 1: Write the driver**

```python
# paper5/code/run_lstm_sizing.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yahoo 5-asset sweep: does vol-target sizing on the LSTM signal raise its risk-adjusted profit?
Compares raw-LSTM / LSTM+vol-target {0.10,0.15,0.30} / fixed-rule on the diversified 5-asset sweet
spot (SPY/TLT/GLD/BTC-USD/UUP), leak-free, net @10bps, hard band. Reports IR, annualized %, maxDD,
and realized vol (to read profit at matched risk). Saves fig_lstm_sizing.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models, band_eval, lstm_sizing

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
FIVE = ["SPY", "TLT", "GLD", "BTC-USD", "UUP"]


def _rule_positions(df):
    ret = df.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(PPY)
    pos = (np.sign(df.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
    return pos.ewm(span=5, min_periods=1).mean().to_numpy().T


def _metrics(POS, fwd, idx, band, n_trials):
    N = POS.shape[0]
    W = band_eval.apply_band(POS.T, band) / N
    net = costs.net_returns(W[np.asarray(idx)], np.asarray(fwd).T[np.asarray(idx)], 10.0, 0.0)
    net = net[np.isfinite(net)]
    eq = float(np.prod(1.0 + net))
    ann = eq ** (PPY / len(net)) - 1.0
    return {"ir": metrics.ann_ir(net, PPY), "ann": ann, "mdd": metrics.max_drawdown(net),
            "vol": float(np.std(net) * np.sqrt(PPY)),
            "dsr": metrics.deflated_sharpe(net, n_trials, PPY)}


def main():
    df = combined_data.fetch_combined_daily()[FIVE].dropna(how="any")
    X, fwd, dates_ms = crypto_features.build(df)
    T = X.shape[1]
    vol = (df.pct_change().rolling(30).std() * np.sqrt(PPY)).shift(1).to_numpy().T
    vol = np.nan_to_num(vol, nan=1.0)
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {len(FIVE)} assets {FIVE}, {T} bars {df.index[0].date()}..{df.index[-1].date()}, folds={len(folds)}")

    POS_l, _, idx = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds,
                                                  warm=252, epochs=300)
    POS_r = _rule_positions(df)
    nL = len(models.LSTM_GRID)

    rows = [("LSTM raw", _metrics(POS_l, fwd, idx, 0.3, nL))]
    for tv in (0.10, 0.15, 0.30):
        rows.append((f"LSTM vt{tv:.2f}", _metrics(lstm_sizing.size_positions(POS_l, vol, tv), fwd, idx, 0.3, nL)))
    rows.append(("fixed-rule", _metrics(POS_r, fwd, idx, 0.3, 1)))

    print(f"\n{'variant':<14}{'netIR':>8}{'ann%':>8}{'maxDD':>8}{'realVol':>9}{'DSR':>7}")
    print("-" * 54)
    for nm, m in rows:
        print(f"{nm:<14}{m['ir']:>8.2f}{m['ann']*100:>7.1f}%{m['mdd']:>8.0%}{m['vol']*100:>8.1f}%{m['dsr']:>7.2f}")

    fig, ax = plt.subplots(figsize=(10, 4.6))
    labels = [nm for nm, _ in rows]
    ax.bar(labels, [m["ir"] for _, m in rows], color="#2563eb")
    ax.axhline(rows[-1][1]["ir"], ls="--", color="#64748b", lw=1, label=f"rule IR {rows[-1][1]['ir']:.2f}")
    ax.set_ylabel("net IR @10bps"); ax.set_title("LSTM + vol-target sizing sweep (Yahoo 5-asset, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_lstm_sizing.png"), dpi=130); plt.close()
    print("\n[fig] figures/fig_lstm_sizing.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the driver**

Run: `cd paper5/code && python -u run_lstm_sizing.py`
Expected: a data line and a 5-row table (LSTM raw / vt0.10 / vt0.15 / vt0.30 / fixed-rule) with
netIR/ann%/maxDD/realVol/DSR, plus `[fig] figures/fig_lstm_sizing.png`. Several minutes (LSTM training).

- [ ] **Step 3: Sanity-check & record the best dial**

Compare LSTM raw vs the vt rows: did vol-target sizing raise the IR? Read profit **at matched
realVol** (e.g., the vt whose realVol matches the rule's — compare their ann%). Note which `target_vol`
gives the best IR (call it `BEST_TV` — used in L3). Do not tune to force a win.

- [ ] **Step 4: Commit (driver + figure)**

```bash
git add paper5/code/run_lstm_sizing.py
git add -f paper5/figures/fig_lstm_sizing.png
git commit -m "feat(paper5): LSTM vol-target sizing sweep on Yahoo 5-asset (raw vs sized vs rule)"
```

---

## Task L3: eToro real-price validation of the best dial

**Files:**
- Create: `paper5/engine/etoro_lstm_sized.py`

No unit test (network + training). Run by the controller with `--tv BEST_TV` from L2.

- [ ] **Step 1: Write the validation driver**

```python
# paper5/engine/etoro_lstm_sized.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the best vol-target-sized LSTM on REAL eToro prices (5-asset sweet spot, real per-asset
spreads), next to the fixed-rule. Read-only. Usage: python etoro_lstm_sized.py [--tv 0.15]"""
import sys, os, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (os.path.join(HERE, "..", "code"), os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"), os.path.join(HERE, "..", "..", "back")):
    sys.path.insert(0, os.path.abspath(_p))
import etoro_gbt_backtest as eb
import train_eval, models, lstm_sizing, band_eval, metrics, etoro_backtest, instrument_map
from etoro_api.server import get_server_client

FIVE = ["SPY", "TLT", "GLD", "BTC-USD", "UUP"]


def _ann(net, ppy):
    eq = float(np.prod(1.0 + net)); return eq ** (ppy / len(net)) - 1.0


def main(tv):
    client = get_server_client()

    def search(t):
        sym = t.replace("-USD", "")
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={sym}")
        items = r.get("items") if isinstance(r, dict) else None
        return items[0].get("internalInstrumentId") if items else None

    mapping, missing = instrument_map.resolve(FIVE, search)
    ids = list(mapping.values()); id2tk = {v: k for k, v in mapping.items()}
    close, dates, kept = etoro_backtest.build_closes(lambda iid: client.request(
        "GET", f"/api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000"), ids)
    print(f"[resolve] kept {[id2tk[i] for i in kept]}  missing={missing}")
    X, fwd, dates_ms, vol, ppy, df = eb.panel_to_xy(close, dates)
    T = X.shape[1]
    spread = eb._spread_vec(client, kept)
    folds = train_eval.make_folds(T, warm=126, first_train=400, step=200)
    POS_l, _, idx = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds,
                                                  warm=126, epochs=300)
    POS_r = eb._rule_positions(df, ppy)
    N = X.shape[0]

    def evalp(POS, band):
        W = band_eval.apply_band(POS.T, band) / N
        net = eb.net_per_asset(W[np.asarray(idx)], np.asarray(fwd).T[np.asarray(idx)], spread)
        net = net[np.isfinite(net)]
        return metrics.ann_ir(net, ppy), _ann(net, ppy), metrics.max_drawdown(net)

    print(f"\n[eToro 5-asset, tv={tv}]  {'variant':<16}{'netIR':>8}{'ann%':>8}{'maxDD':>8}")
    for nm, POS in [("fixed-rule", POS_r), ("LSTM raw", POS_l),
                    (f"LSTM vt{tv:.2f}", lstm_sizing.size_positions(POS_l, vol, tv))]:
        ir, ann, mdd = evalp(POS, 0.3)
        print(f"{'':<26}{nm:<16}{ir:>8.2f}{ann*100:>7.1f}%{mdd:>8.0%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tv", type=float, default=0.15); a = ap.parse_args()
    main(a.tv)
```

- [ ] **Step 2: Run with the best dial from L2 (controller; network + back/.env keys)**

Run: `cd paper5/engine && python -u etoro_lstm_sized.py --tv <BEST_TV>`
Expected: a `[resolve]` line (5 assets, likely all kept) and a 3-row table (fixed-rule / LSTM raw /
LSTM vt) with netIR/ann%/maxDD on real eToro prices + real spreads.

- [ ] **Step 3: Commit**

```bash
git add paper5/engine/etoro_lstm_sized.py
git commit -m "feat(paper5): eToro real-price validation of vol-target-sized LSTM (5-asset)"
```

---

## Task L4: Record the result (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (paper5 findings — targeted Edit; parallel session also edits this file)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the outcome to `etoro/CLAUDE.md`**

Add one bullet: did vol-target sizing raise the LSTM's IR (Yahoo sweep numbers: raw vs best vt vs rule);
profit at matched risk; and the eToro real-price validation (sized-LSTM vs rule). Fill from L2/L3
output; do not invent. Targeted Edit anchored on existing text.

- [ ] **Step 2: Update memory** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line with the sized-LSTM result + verdict. (Memory files outside the repo — Write tool.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record LSTM vol-target sizing outcome"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 3 modules (lstm_sizing + run_lstm_sizing + eToro validation; torch training & paper4 untouched) -> Tasks L1-L4. ✓
- Spec section 4 wrapper (`clip(LSTM*target_vol/vol, +/-2)` + per-asset EWM; band downstream) -> Task L1. ✓
- Spec section 2 decisions (5-asset SPY/TLT/GLD/BTC-USD/UUP; dial 0.10/0.15/0.30; Yahoo-deep sweep then eToro best; criterion IR + realized vol) -> Task L2 (`FIVE`, dial loop, `_metrics` returns ir/ann/mdd/vol/dsr) + Task L3 (eToro best). ✓
- Spec section 5 sweep/comparison/eToro (table with realized vol, figure, rule reference, best-config eToro validation) -> Task L2 + L3. ✓
- Spec section 6 testing (zero-tv->0, inverse-vol, clip, smoothing) -> Task L1 tests. ✓
- Spec section 7 conventions (serving-time, no retraining, untouched training, add -f figure) -> Context + steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". `BEST_TV` / `<...>` are experiment outputs from L2 used in L3/L4; instructions say fill from output. Acceptable.

**3. Type consistency:** `size_positions(POS, vol, target_vol=0.15, clip=2.0, ewm_span=5)` (L1) called in L2/L3 as `size_positions(POS_l, vol, tv)`. `_metrics(POS, fwd, idx, band, n_trials)` (L2) returns `ir/ann/mdd/vol/dsr`, consumed in the print loop. `nested_walkforward(...)->(POS, chosen, test_idx)` unpacked as `POS_l, _, idx`. `_rule_positions(df)` (L2, PPY-fixed) vs `eb._rule_positions(df, ppy)` (L3, ppy-arg) — both return `(N,T)`; L3 uses the eToro helper's signature correctly. `eb.{panel_to_xy,_spread_vec,net_per_asset}` signatures match their use. `band_eval.apply_band(POS.T, band)` consistent. All consistent. ✓
```
