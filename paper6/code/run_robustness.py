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
