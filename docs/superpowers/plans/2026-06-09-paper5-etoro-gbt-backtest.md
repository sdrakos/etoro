# eToro Real-Price GBT Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the winning GBT model (and the LSTM and the rule) on real eToro daily candles with real per-asset spreads — a read-only, leak-free walk-forward backtest answering "does the edge survive on the broker?".

**Architecture:** A new `paper5/engine/etoro_gbt_backtest.py`. Pure helpers (`net_per_asset`, `panel_to_xy`) are offline-unit-tested; the live `run()` resolves the basket to eToro instruments, fetches ~1000 daily candles (reusing paper4's candle helpers), builds features, runs GBT/LSTM/rule, charges real per-asset spreads, and prints the comparison + figure. paper4 is imported, never modified. READ-ONLY eToro (candles/search/rates; no orders).

**Tech Stack:** Python 3.11+, NumPy/pandas, scikit-learn, PyTorch (LSTM), the eToro demo client. Tests: pytest, offline (the network path is exercised only by the driver run).

---

## Context for the implementer (read once)

cwd `etoro/`. The new file lives in `paper5/engine/` (bare-import convention: no `__init__.py`; tests in `paper5/engine/tests/`, run `python -m pytest` from `paper5/engine/`). Do NOT modify `paper4/` (import only). Commits: clean, NO `Co-Authored-By`. Figures: `git add -f`. Secrets only in `back/.env` — never print them.

**Reusable pieces (all import-only):**
- `paper4/engine/etoro_backtest.py`: `parse_candles(raw) -> [(date,'YYYY-MM-DD', close)]` and `build_closes(fetch_raw, ids) -> (close (T,N), dates, ids_kept)`.
- `paper4/engine/instrument_map.py`: `resolve(tickers, search) -> (mapping {ticker:id}, missing)`.
- `back/etoro_api/server.py`: `get_server_client()` (demo client; `.request("GET", path)`).
- `paper5/code/`: `crypto_features.build(close_df) -> (X (N,T,10), fwd (N,T), dates_ms)`, `gbt_model.gbt_positions(X, fwd, vol, folds, warm) -> (POS, test_idx)`, `train_eval.make_folds` / `train_eval.nested_walkforward(make, grid, X, fwd, folds, warm, epochs)`, `band_eval.apply_band(pos_TN, band)`, `models.make_lstm`/`LSTM_GRID`.
- `paper4/code/metrics.py`: `ann_ir`, `newey_west_t`, `deflated_sharpe`, `durability_by_year`, `max_drawdown`.

**The eToro endpoints (read-only):**
- search: `GET /api/v1/market-data/search?internalSymbolFull={SYM}` -> `items[0]["internalInstrumentId"]`.
- candles: `GET /api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000`.
- rates (spreads): `GET /api/v1/market-data/instruments/rates?instrumentIds={comma_ids}` -> list with bid/ask.

**The 18-asset basket** (Yahoo tickers; crypto strip `-USD` for eToro search):
`("BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","LTC-USD","DOGE-USD","SPY","QQQ","EEM","EFA","TLT","IEF","GLD","DBC","UUP","XLE")`.

**sys.path preamble** every file in `paper5/engine/` needs (so all the above import):
```python
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "code"),
           os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"),
           os.path.join(HERE, "..", "..", "back")):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)
```

---

## File Structure

- `paper5/engine/etoro_gbt_backtest.py` — **create**: `BASKET`, `net_per_asset`, `panel_to_xy` (offline), plus the live `run()`/`main()` (network).
- `paper5/engine/tests/test_etoro_gbt_backtest.py` — **create**: offline tests for `net_per_asset` + `panel_to_xy`.

---

## Task E1: Offline helpers (net_per_asset + panel_to_xy)

**Files:**
- Create: `paper5/engine/etoro_gbt_backtest.py`
- Create: `paper5/engine/tests/test_etoro_gbt_backtest.py`

- [ ] **Step 1: Write the failing tests**

```python
# paper5/engine/tests/test_etoro_gbt_backtest.py
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import etoro_gbt_backtest as eb


def test_net_per_asset_zero_turnover_zero_cost():
    T, N = 5, 3
    W = np.zeros((T, N))
    fwd = np.zeros((T, N))
    net = eb.net_per_asset(W, fwd, np.array([10.0, 10.0, 10.0]))
    assert net.shape == (T,)
    assert np.allclose(net, 0.0)


def test_net_per_asset_higher_spread_lowers_net():
    T, N = 4, 2
    # asset 0 flips +/-1 each day (high turnover), asset 1 flat; positive gross
    W = np.array([[1.0, 0.5], [-1.0, 0.5], [1.0, 0.5], [-1.0, 0.5]])
    fwd = np.full((T, N), 0.01)
    lo = eb.net_per_asset(W, fwd, np.array([1.0, 1.0]))
    hi = eb.net_per_asset(W, fwd, np.array([200.0, 1.0]))   # huge spread on the churny asset
    assert hi.sum() < lo.sum()


def test_panel_to_xy_shapes():
    T, N = 400, 3
    base = np.linspace(1.0, 3.0, T)
    close = np.outer(base, np.arange(1, N + 1))
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2021-01-01", periods=T)]
    X, fwd, dates_ms, vol, ppy, df = eb.panel_to_xy(close, dates)
    assert X.shape == (N, T, 10)
    assert fwd.shape == (N, T)
    assert vol.shape == (N, T)
    assert np.isfinite(X).all() and np.isfinite(vol).all()
    assert ppy > 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd paper5/engine && python -m pytest tests/test_etoro_gbt_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'etoro_gbt_backtest'`.

- [ ] **Step 3: Implement the module skeleton + helpers**

```python
# paper5/engine/etoro_gbt_backtest.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only eToro real-price backtest of the GBT (and LSTM and fixed-rule) on the 18-asset basket.
Resolves tickers -> eToro instruments, fetches ~1000 daily candles, builds the 10 features, runs a
leak-free walk-forward, and charges REAL per-asset eToro spreads. NO orders are placed (candles +
search + rates only). Pure helpers are unit-tested; run() hits the live demo client."""
from __future__ import annotations
import sys, os
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "code"),
           os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"),
           os.path.join(HERE, "..", "..", "back")):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)
import crypto_features  # paper5/code

BASKET = ("BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD",
          "SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE")


def net_per_asset(W, fwd, spread_bps_vec, short_fin_annual=0.0):
    """W, fwd: (T,N) weights and next-bar returns. spread_bps_vec: (N,). Returns net stream (T,).
    Charges each asset's own spread on its own turnover (eToro spreads differ a lot per asset)."""
    W = np.asarray(W, float); fwd = np.asarray(fwd, float)
    gross = np.nansum(W * fwd, axis=1)
    turn = np.empty_like(W)
    turn[0] = np.abs(W[0])
    if len(W) > 1:
        turn[1:] = np.abs(W[1:] - W[:-1])
    cost = np.nansum(turn * (np.asarray(spread_bps_vec, float) / 1e4), axis=1)
    fin = (short_fin_annual / 1e4 / 252.0) * np.nansum(np.clip(-W, 0.0, None), axis=1)
    return gross - cost - fin


def panel_to_xy(close_2d, dates):
    """close_2d (T,N) + dates ['YYYY-MM-DD'] -> (X (N,T,10), fwd (N,T), dates_ms, vol (N,T causal),
    ppy, df). vol is annualised trailing-30 realized vol, shifted 1 bar (causal)."""
    idx = pd.to_datetime(dates)
    df = pd.DataFrame(np.asarray(close_2d, float), index=idx).ffill().dropna(how="all")
    X, fwd, dates_ms = crypto_features.build(df)
    days = (df.index[-1] - df.index[0]).days or 1
    ppy = len(df) / days * 365.0
    ret = df.pct_change()
    vol = (ret.rolling(30).std() * np.sqrt(ppy)).shift(1).to_numpy().T
    vol = np.nan_to_num(vol, nan=1.0)
    return X, fwd, dates_ms, vol, ppy, df
```

- [ ] **Step 4: Run the tests**

Run: `cd paper5/engine && python -m pytest tests/test_etoro_gbt_backtest.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add paper5/engine/etoro_gbt_backtest.py paper5/engine/tests/test_etoro_gbt_backtest.py
git commit -m "feat(paper5): eToro backtest offline helpers (per-asset net + panel->features)"
```

---

## Task E2: Live run() + main() (read-only eToro) + execute

**Files:**
- Modify: `paper5/engine/etoro_gbt_backtest.py` (append the live path)

No unit test (network + credentials). The controller runs it.

- [ ] **Step 1: Append the live `run()` and `main()` to `etoro_gbt_backtest.py`**

```python
def _spread_vec(client, kept_ids):
    """Per-asset round-trip spread (bps) from live /rates bid/ask; fallback 10 bps if missing."""
    out = {iid: 10.0 for iid in kept_ids}
    try:
        rr = client.request("GET", "/api/v1/market-data/instruments/rates?instrumentIds="
                            + ",".join(str(i) for i in kept_ids))
        rates = rr.get("rates") if isinstance(rr, dict) else rr
        for it in (rates or []):
            iid = it.get("instrumentID") or it.get("instrumentId") or it.get("internalInstrumentId")
            bid = next((v for k, v in it.items() if k.lower() in ("bid", "sellrate", "sell") and isinstance(v, (int, float))), None)
            ask = next((v for k, v in it.items() if k.lower() in ("ask", "buyrate", "buy") and isinstance(v, (int, float))), None)
            if iid in out and bid and ask:
                out[iid] = (ask - bid) / ((ask + bid) / 2) * 1e4
    except Exception as e:
        print(f"[spread] fallback 10bps ({type(e).__name__})")
    return np.array([out[i] for i in kept_ids], float)


def _eval(POS, fwd, dates_ms, test_idx, band, spread_vec, ppy):
    import band_eval, metrics
    N = POS.shape[0]
    W = band_eval.apply_band(POS.T, band) / N
    F = np.asarray(fwd).T
    rows = np.asarray(test_idx)
    net = net_per_asset(W[rows], F[rows], spread_vec)
    d = np.asarray(dates_ms)[rows]
    fin = np.isfinite(net); net, d = net[fin], d[fin]
    return {"ir": metrics.ann_ir(net, ppy), "t": metrics.newey_west_t(net),
            "dsr": metrics.deflated_sharpe(net, 1, ppy), "mdd": metrics.max_drawdown(net)}


def _rule_positions(df, ppy):
    ret = df.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(ppy)
    pos = (np.sign(df.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
    return pos.ewm(span=5, min_periods=1).mean().to_numpy().T   # (N,T)


def run(tickers=BASKET):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    import train_eval, gbt_model, models
    from etoro_api.server import get_server_client
    import etoro_backtest, instrument_map
    client = get_server_client()

    def search(t):
        sym = t.replace("-USD", "")
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={sym}")
        items = r.get("items") if isinstance(r, dict) else None
        return items[0].get("internalInstrumentId") if items else None

    mapping, missing = instrument_map.resolve(list(tickers), search)
    ids = list(mapping.values()); id2tk = {v: k for k, v in mapping.items()}

    def fetch_raw(iid):
        return client.request("GET", f"/api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000")

    close, dates, kept = etoro_backtest.build_closes(fetch_raw, ids)
    print(f"[resolve] kept {len(kept)}/{len(tickers)}: {[id2tk[i] for i in kept]}  missing={missing}")
    X, fwd, dates_ms, vol, ppy, df = panel_to_xy(close, dates)
    T = X.shape[1]
    spread_vec = _spread_vec(client, kept)
    print(f"[spreads bps] " + ", ".join(f"{id2tk[i]}:{s:.0f}" for i, s in zip(kept, spread_vec)))
    print(f"[data] {len(kept)} assets, {T} bars, {dates[0]}..{dates[-1]}, ppy~{ppy:.0f}")

    folds = train_eval.make_folds(T, warm=126, first_train=400, step=200)
    POS_g, idx = gbt_model.gbt_positions(X, fwd, vol, folds, warm=126)
    POS_l, _, _ = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds, warm=126, epochs=300)
    POS_r = _rule_positions(df, ppy)

    rows = []
    for name, POS in [("fixed-rule", POS_r), ("LSTM-DMN", POS_l), ("GBT", POS_g)]:
        for band, tag in [(0.0, "none"), (0.3, "hard")]:
            r = _eval(POS, fwd, dates_ms, idx, band, spread_vec, ppy)
            rows.append((name, tag, r["ir"], r["t"], r["dsr"], r["mdd"]))

    print(f"\n{'model':<12}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'maxDD':>8}")
    print("-" * 50)
    for nm, bd, ir, t, dsr, mdd in rows:
        print(f"{nm:<12}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{mdd:>8.0%}")

    FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    pal = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "GBT": "#16a34a"}
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.bar(labels, irs, color=[pal[r[0]] for r in rows])
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR (real eToro prices + per-asset spreads)")
    ax.set_title(f"eToro real-price backtest — {len(kept)} assets, ~{T} bars")
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_etoro_gbt_backtest.png"), dpi=130); plt.close()
    print("\n[fig] paper5/figures/fig_etoro_gbt_backtest.png")


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Re-run the offline tests (the appended live code must not break imports)**

Run: `cd paper5/engine && python -m pytest tests/test_etoro_gbt_backtest.py -v`
Expected: PASS (3 passed — the live code is only reached via `run()`/`__main__`).

- [ ] **Step 3: Run the live backtest (controller; needs network + back/.env eToro keys)**

Run: `cd paper5/engine && python -u etoro_gbt_backtest.py`
Expected: a `[resolve]` line (kept ~16-17/18, DBC likely missing), a `[spreads bps]` line, a `[data]` line, the 6-row table (fixed-rule/LSTM/GBT x none/hard with netIR/NW-t/DSR/maxDD), and `[fig] ...`. If the eToro client fails to auth, report the error (do not hardcode keys).

- [ ] **Step 4: Sanity-check & commit**

Read the table: does the GBT (best band) net IR stay positive (NW-t > 1.5) on real prices? How do
GBT/LSTM/rule compare on the same broker? Note the per-asset spreads (crypto ~high). Then:

```bash
git add paper5/engine/etoro_gbt_backtest.py
git add -f paper5/figures/fig_etoro_gbt_backtest.png
git commit -m "feat(paper5): read-only eToro real-price backtest of GBT/LSTM/rule with real per-asset spreads"
```

---

## Task E3: Record the result (CLAUDE.md + memory)

**Files:**
- Modify: `etoro/CLAUDE.md` (paper5 findings — targeted Edit; parallel session also edits this file)
- Modify: memory `paper5-intraday-momentum.md`

- [ ] **Step 1: Append the eToro real-price outcome to `etoro/CLAUDE.md`**

Add one bullet with the measured GBT/LSTM/rule net IR on real eToro prices (best band), the kept/missing
universe, the per-asset spread range, and whether the GBT edge survived. Fill from Task E2's output; do
not invent. Use a targeted Edit anchored on existing text.

- [ ] **Step 2: Update memory** `C:\Users\Στέφανος\.claude\projects\C--Users----------agel-openai-AGENTI-SDK-etoro\memory\paper5-intraday-momentum.md`

Append one line: the eToro real-price result + verdict. (Memory files are outside the repo — Write tool.)

- [ ] **Step 3: Commit**

```bash
git add etoro/CLAUDE.md
git commit -m "docs(paper5): record eToro real-price GBT backtest outcome"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Spec section 3 module (etoro_gbt_backtest with resolve/fetch/features/models/net/metrics/figure; paper4 import-only; read-only) -> Tasks E1 (helpers) + E2 (run). ✓
- Spec section 4 `net_per_asset` (per-asset spread on per-asset turnover) -> Task E1. ✓
- Spec section 2 locked decisions (full walk-forward on eToro prices; real per-asset spreads via /rates; universe = resolvable subset, crypto `-USD` stripped; GBT/LSTM/rule both bands) -> Task E2 (`run`: resolve+strip, `_spread_vec`, `make_folds`, three models, both bands). ✓
- Spec section 5 eval/comparison (table netIR/NW-t/DSR/maxDD, resolved/missing + spreads printed, figure, PPY from bars/year) -> Task E2 `_eval`/print/figure + `panel_to_xy` ppy. ✓
- Spec section 6 testing (net_per_asset zero/high-spread/shape; panel_to_xy shapes; live path integration-only) -> Task E1 tests; E2 has no unit test (network), run by controller. ✓
- Spec section 7 conventions (read-only, secrets in back/.env, paper4 untouched, add -f figure) -> Context + steps. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases". `<...>` numbers in E3 are experiment outputs unavailable before E2 runs. The `_spread_vec` fallback to 10 bps is explicit, not a placeholder. Acceptable.

**3. Type consistency:** `net_per_asset(W, fwd, spread_bps_vec, short_fin_annual=0.0)` (E1) used by `_eval` (E2) with `(W[rows], F[rows], spread_vec)`. `panel_to_xy(close_2d, dates) -> (X, fwd, dates_ms, vol, ppy, df)` (E1) consumed in `run` (E2) with exactly those 6 returns. `gbt_model.gbt_positions(X, fwd, vol, folds, warm) -> (POS, test_idx)`, `nested_walkforward(make, grid, X, fwd, folds, warm, epochs)` (returns POS, chosen, idx — `run` unpacks `POS_l, _, _`), `_rule_positions(df, ppy) -> (N,T)`. `_eval(...)` returns `ir/t/dsr/mdd`, consumed in the print loop. `metrics.{ann_ir,newey_west_t,deflated_sharpe,max_drawdown}` exist in paper4. All consistent. ✓
```
