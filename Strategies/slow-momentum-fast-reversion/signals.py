"""Momentum primitives + three weight builders sharing one cross-sectional constructor.
All builders return (T,N) dollar-neutral weight matrices, zeroed during warmup."""
from __future__ import annotations
import numpy as np


def zscore_xs(x):
    m = np.nanmean(x); s = np.nanstd(x) + 1e-9
    return (x - m) / s


def xs_weights(score, k):
    """Long top-k, short bottom-k, equal weight, dollar-neutral, gross=1."""
    w = np.zeros(len(score), dtype=float)
    valid = np.where(np.isfinite(score))[0]
    if len(valid) < 2 * k:
        return w
    order = valid[np.argsort(score[valid])]
    w[order[-k:]] = 0.5 / k
    w[order[:k]] = -0.5 / k
    return w


def momentum_matrix(close, lookback=252, skip=21):
    """(T,N) classic 12-1 momentum: close[t-skip]/close[t-lookback]-1, nan before warmup."""
    T, N = close.shape
    M = np.full((T, N), np.nan)
    for t in range(lookback, T):
        M[t] = close[t - skip] / close[t - lookback] - 1.0
    return M


def build_weights(variant, close, vel, trend_sig, sev, k, warmup=252,
                  sig_thresh=1.0, sev_floor=0.2):
    """Return (T,N) weights for one of: tsmom | cpd_momentum | belief_gated.

    tsmom        : score = 12-1 momentum; full gross.
    cpd_momentum : score = Kalman velocity; gross scaled by time-varying (1 - severity).
    belief_gated : velocity ranking, but ONLY among names whose trend is statistically
                   significant (|trend_sig| >= sig_thresh); time-varying severity gross gate.
                   Significance changes WHICH names trade (book composition), so it moves IR
                   — a magnitude multiplier would not, since xs_weights is rank-based and
                   normalizes magnitude away. This is what distinguishes it from cpd_momentum.
    """
    T, N = close.shape
    W = np.zeros((T, N))
    mom = momentum_matrix(close, lookback=warmup, skip=21) if variant == "tsmom" else None
    for t in range(warmup, T):
        if variant == "tsmom":
            score = zscore_xs(mom[t])
            gate = 1.0
        elif variant == "cpd_momentum":
            score = zscore_xs(vel[t])
            gate = 1.0 - np.nanmean(sev[t])
        elif variant == "belief_gated":
            score = zscore_xs(vel[t])
            score[np.abs(trend_sig[t]) < sig_thresh] = np.nan   # drop insignificant trends
            gate = 1.0 - np.nanmean(sev[t])
        else:
            raise ValueError(f"unknown variant {variant!r}")
        gate = max(gate, sev_floor)         # never fully flat; keep some exposure
        W[t] = xs_weights(score, k) * gate
    return W
