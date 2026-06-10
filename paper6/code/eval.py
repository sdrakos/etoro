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
