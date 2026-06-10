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
