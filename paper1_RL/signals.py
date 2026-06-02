# paper1_RL/signals.py
"""Pure signal functions (no IO). Fixed theory-driven signs — ΧΩΡΙΣ learning
(το paper απεδειξε learning -> overfit)."""
from __future__ import annotations
import numpy as np

def zscore_xs(x: np.ndarray) -> np.ndarray:
    """Cross-sectional z-score (ignore nan)."""
    m = np.nanmean(x); s = np.nanstd(x) + 1e-9
    return (x - m) / s

def momentum_12_1(close: np.ndarray, t: int) -> np.ndarray:
    """12-1 momentum (skip last month). Requires t >= 252."""
    return close[t - 21] / close[t - 252] - 1

def sector_neutral(score: np.ndarray, sectors: np.ndarray) -> np.ndarray:
    """Demean το score ΕΝΤΟΣ καθε sector (εξουδετερωνει sector bet -> momentum crash)."""
    out = score.astype(float).copy()
    for sec in np.unique(sectors):
        mask = sectors == sec
        out[mask] = out[mask] - np.nanmean(out[mask])
    return out

def vix_theta_scale(weights: np.ndarray, vix_now: float, vix_ref: float,
                    lo: float = 0.3, hi: float = 1.5) -> np.ndarray:
    """Practical state-dependent θ: scale exposure ~ vix_ref/vix_now, clipped.
    Υψηλο VIX -> μικροτερο scale -> de-risk."""
    if not np.isfinite(vix_now) or vix_now <= 0:
        return weights
    scale = np.clip(vix_ref / vix_now, lo, hi)
    return weights * scale

def pead_signal_at(surprise_mat: np.ndarray, t: int) -> np.ndarray:
    """Το cross-sectional surprise vector την ημερα t (απο το drift matrix)."""
    return surprise_mat[t]
