"""Axis 4 driver: for each preset, run the base rule on the real basket and report
net-IR, realized maxDD, and EUR end-value on EUR10k. Net-of-cost, leak-free."""
from __future__ import annotations
import numpy as np

# Import paper6-local modules FIRST so `data`/`eval`/`rule` resolve to paper6's copies
# (paper4/code also has a `data.py`; these locals pull in `_paths` internally before any
# band_eval/costs use). Then the paper4/paper5 helpers are already path-resolved + cached.
import data
import eval as ev
import rule
import sizing_dial

import _paths  # noqa: F401 — must precede band_eval bare import
import band_eval   # noqa: E402  (paper5/code)

BASE = {"lookback": 252, "smooth_span": 5, "band": 0.15}


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
        # EUR uses the SAME per-asset-spread cost model as the net-IR column (not a flat mean)
        W = band_eval.apply_band(pos, BASE["band"])[rows] / N
        net = ev._net_with_per_asset_spreads(W, fwd[rows], spreads)
        eur = sizing_dial.eur_end_value(net)
        print(f"{name:14} {cfg['target_vol']:5.2f} {m['net_ir']:8.2f} {m['max_dd']:8.2%} {eur:10.0f}")


if __name__ == "__main__":
    main()
