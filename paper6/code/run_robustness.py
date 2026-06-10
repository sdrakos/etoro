"""Axis 1 driver: sweep the rule on the real 5-asset basket, leak-free WF, net-of-cost,
emit the net-IR heatmap and print the stable-center base config."""
from __future__ import annotations
import os

import numpy as np

import data
import eval as ev
import robustness
import rule

GRID = {"lookback": [21, 42, 63, 126, 252],
        "band": [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80],
        "target_vol": [0.10, 0.15, 0.20], "smooth_span": [5]}

KNEE_BAND = 0.15  # turnover-control knee; band is a capped DIAL (monotone net-IR tail), not optimized — paper5


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
    knee_rows = [r for r in rows if r["band"] == KNEE_BAND]
    base = robustness.robust_pick(knee_rows, knobs=["lookback", "target_vol"], neighbor_span=1)
    print(f"[axis1] base config (band fixed at knee {KNEE_BAND}, lookback/target_vol robust): {base}")
    print(f"[axis1] (for contrast) argmax over full grid: {max(rows, key=lambda r: r['net_ir'])}")
    lb0, tv0 = base["lookback"], base["target_vol"]
    curve = [(r["band"], round(r["net_ir"], 3)) for r in sorted(
        (r for r in rows if r["lookback"] == lb0 and r["target_vol"] == tv0),
        key=lambda r: r["band"])]
    print(f"[axis1] band->net_IR curve at lookback={lb0}, target_vol={tv0}: {curve}")
    # 2-panel figure: net-IR surface (lookback x band) + the band dial curve at the base lookback
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tv = base["target_vol"]; lb0 = base["lookback"]
    lbs, bands = GRID["lookback"], GRID["band"]
    heat = np.array([[next(r["net_ir"] for r in rows if r["lookback"] == lb and r["band"] == bd
                          and r["target_vol"] == tv) for bd in bands] for lb in lbs])
    curve = [next(r["net_ir"] for r in rows if r["lookback"] == lb0 and r["band"] == bd
                  and r["target_vol"] == tv) for bd in bands]
    fig, (axh, axc) = plt.subplots(1, 2, figsize=(13, 5))
    im = axh.imshow(heat, aspect="auto", cmap="viridis", origin="lower")
    fig.colorbar(im, ax=axh, label="net IR")
    axh.set_xticks(range(len(bands))); axh.set_xticklabels(bands, rotation=45)
    axh.set_yticks(range(len(lbs))); axh.set_yticklabels(lbs)
    axh.set_xlabel("no-trade band"); axh.set_ylabel("lookback (days)")
    axh.set_title(f"net IR surface (target_vol={tv})")
    axh.axvline(bands.index(KNEE_BAND), color="red", ls="--", lw=1)
    axc.plot(bands, curve, "o-")
    axc.axvline(KNEE_BAND, color="red", ls="--", lw=1, label=f"knee={KNEE_BAND} (base)")
    axc.set_xlabel("no-trade band"); axc.set_ylabel("net IR")
    axc.set_title(f"band is a turnover DIAL (lookback={lb0}): monotone, capped at knee")
    axc.legend()
    fig.suptitle("paper6 Axis1 robustness — base = plateau interior at the band knee, not the argmax")
    out = os.path.join(os.path.dirname(__file__), "..", "figures", "fig_robustness.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.tight_layout(); fig.savefig(out, dpi=120)
    print(f"[axis1] wrote {out}")


if __name__ == "__main__":
    main()
