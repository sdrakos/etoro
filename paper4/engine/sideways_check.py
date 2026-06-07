"""Does the model step aside in sideways (range-bound) regimes? An empirical check on real eToro prices.

We classify each (asset, day) as sideways / mixed / trending by the Kaufman EFFICIENCY RATIO over a
63-day window --- ER = |P_t - P_{t-n}| / sum|dP| --- which is INDEPENDENT of the model's own trend
signal (so the test is not circular). Then, per regime, we compare two positions:
  * naive  = sign(trend)            -- a dumb trend follower, full size regardless of confidence;
  * model  = tanh(trend_significance) -- the significance-aware position the DMN learns (shrinks when
             the Kalman trend is weak/uncertain), the actual mechanism documented in the paper.
We report mean |position|, turnover, and net-of-next-day P&L per regime. The honest claim: in
sideways the model SHRINKS exposure and avoids whipsaw losses; it does not profit from the range.

CLI:  python paper4/engine/sideways_check.py SPY TLT GLD USO UUP
"""
from __future__ import annotations
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.abspath(os.path.join(HERE, "..", "code"))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from etoro_backtest import _fetch_etoro_closes, _ffill   # noqa: E402
from features import build_features                       # noqa: E402

TREND_SIG_IDX, SEV_IDX = 7, 9    # feature indices in build_features' X (N,T,F)


def efficiency_ratio(close, n=63):
    """Kaufman efficiency ratio per (t, asset): |net move| / |gross path| over a trailing n days.
    ~1 = clean trend, ~0 = choppy/sideways. close is (T,N); returns (T,N), NaN before warmup."""
    close = np.asarray(close, float)
    T, N = close.shape
    er = np.full((T, N), np.nan)
    dabs = np.abs(np.diff(close, axis=0))                 # (T-1, N)
    for t in range(n, T):
        net = np.abs(close[t] - close[t - n])
        gross = dabs[t - n:t].sum(axis=0) + 1e-12
        er[t] = net / gross
    return er


def regime_masks(er, warm=252):
    """Tercile split of the efficiency ratio into sideways / mixed / trending boolean masks (T,N)."""
    flat = er[warm:].ravel()
    flat = flat[~np.isnan(flat)]
    lo, hi = np.quantile(flat, [1 / 3, 2 / 3])
    valid = np.zeros_like(er, dtype=bool); valid[warm:] = ~np.isnan(er[warm:])
    return {"sideways": valid & (er < lo), "trending": valid & (er > hi),
            "mixed": valid & (er >= lo) & (er <= hi)}, (lo, hi)


def positions(close):
    """Return (naive, model, trend_sig, sev) each (T,N). naive=sign(trend), model=tanh(significance)."""
    X, _fwd = build_features(_ffill(close))               # X (N,T,F)
    tsig = X[:, :, TREND_SIG_IDX].T                        # (T,N)
    sev = X[:, :, SEV_IDX].T
    return np.sign(tsig), np.tanh(tsig), tsig, sev


def run(tickers, tag="sideways"):
    import json
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    close, dates, kept, id2tk = _fetch_etoro_closes(tickers)
    close = _ffill(close)
    er = efficiency_ratio(close)
    masks, (lo, hi) = regime_masks(er)
    naive, model, tsig, sev = positions(close)
    fwd = np.zeros_like(close); fwd[:-1] = close[1:] / close[:-1] - 1.0   # next-day return (T,N)
    dnaive = np.zeros_like(naive); dnaive[1:] = np.abs(naive[1:] - naive[:-1])
    dmodel = np.zeros_like(model); dmodel[1:] = np.abs(model[1:] - model[:-1])

    rows = {}
    print(f"\n=== sideways check [{tag}] — {len(kept)} products, {dates[0]}..{dates[-1]} ===")
    print(f"  efficiency-ratio terciles: sideways <{lo:.2f}, trending >{hi:.2f}")
    print(f"  {'regime':<9} {'|tsig|':>7} {'|pos|naive':>11} {'|pos|model':>11} "
          f"{'turn naive':>11} {'turn model':>11} {'P&L naive':>10} {'P&L model':>10}")
    for r in ("sideways", "mixed", "trending"):
        m = masks[r]
        pnl_n = float((naive * fwd)[m].mean() * 252)
        pnl_m = float((model * fwd)[m].mean() * 252)
        rows[r] = {"abs_tsig": float(np.abs(tsig)[m].mean()),
                   "abs_pos_naive": float(np.abs(naive)[m].mean()),
                   "abs_pos_model": float(np.abs(model)[m].mean()),
                   "turnover_naive": float(dnaive[m].mean()),
                   "turnover_model": float(dmodel[m].mean()),
                   "pnl_naive_ann": pnl_n, "pnl_model_ann": pnl_m, "n": int(m.sum())}
        print(f"  {r:<9} {rows[r]['abs_tsig']:>7.2f} {rows[r]['abs_pos_naive']:>11.2f} "
              f"{rows[r]['abs_pos_model']:>11.2f} {rows[r]['turnover_naive']:>11.3f} "
              f"{rows[r]['turnover_model']:>11.3f} {pnl_n*100:>9.1f}% {pnl_m*100:>9.1f}%")

    FIG = os.path.abspath(os.path.join(HERE, "..", "figures"))
    plt.rcParams.update({"font.family": "serif", "figure.dpi": 150, "savefig.bbox": "tight"})
    regs = ["sideways", "mixed", "trending"]; x = np.arange(3); w = 0.38
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    a1.bar(x - w / 2, [rows[r]["abs_pos_naive"] for r in regs], w, label="naive sign(trend)", color="#9aa0a6")
    a1.bar(x + w / 2, [rows[r]["abs_pos_model"] for r in regs], w, label="model tanh(significance)", color="#1f4e9c")
    a1.set_xticks(x); a1.set_xticklabels(regs); a1.set_ylabel("mean |position|")
    a1.set_title("Exposure by regime"); a1.legend(fontsize=8); a1.grid(alpha=.3, axis="y")
    a2.bar(x - w / 2, [rows[r]["pnl_naive_ann"] * 100 for r in regs], w, label="naive", color="#9aa0a6")
    a2.bar(x + w / 2, [rows[r]["pnl_model_ann"] * 100 for r in regs], w, label="model", color="#1f4e9c")
    a2.axhline(0, color="k", lw=.6); a2.set_xticks(x); a2.set_xticklabels(regs)
    a2.set_ylabel("annualized P&L %"); a2.set_title("P&L by regime (net of next-day move)")
    a2.legend(fontsize=8); a2.grid(alpha=.3, axis="y")
    fig.suptitle(f"Sideways behaviour on real eToro prices — {len(kept)} products", y=1.02)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"fig_{tag}.png")); plt.close(fig)
    with open(os.path.join(HERE, "..", f"results_{tag}.json"), "w", encoding="utf-8") as f:
        json.dump({"tickers": [id2tk[i] for i in kept], "terciles": [lo, hi], "regimes": rows}, f, indent=2)
    print(f"\n  saved figures/fig_{tag}.png + results_{tag}.json")
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Sideways/range-regime behaviour check on real eToro prices.")
    ap.add_argument("tickers", nargs="*", help="product tickers")
    ap.add_argument("--tag", default="sideways")
    a = ap.parse_args()
    run(a.tickers or ["SPY", "TLT", "GLD", "USO", "UUP"], tag=a.tag)
