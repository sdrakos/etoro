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
