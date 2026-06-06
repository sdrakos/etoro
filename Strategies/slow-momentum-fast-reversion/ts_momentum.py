"""Time-series (directional) momentum builder -- the diversified-asset CTA setting.

Each asset is traded long/short on its OWN trend (not ranked against others), unlike the
cross-sectional builder in signals.py. Multi-horizon trend sign, inverse-volatility sizing,
monthly rebalance, gross normalised to 1, optional per-asset BOCPD changepoint de-risk.

This is the rules baseline of paper4 (the yardstick the LSTM Deep Momentum Network must beat).
"""
from __future__ import annotations
import numpy as np


def build_ts_weights(close, sev=None, lookbacks=(21, 63, 126, 252), vol_win=63,
                     target=0.10 / np.sqrt(252.0), rebal=21, gate=False):
    """(T,N) directional weights from a (T,N) close matrix.

    For each asset: signal = mean over `lookbacks` of sign(close[t]/close[t-lb]-1) (multi-horizon
    trend), scaled by target/realised_vol (calmer assets get more notional), normalised so gross
    (sum of |w|) = 1, recomputed every `rebal` days and held in between. If gate is True and a
    per-asset severity matrix `sev` is given, each asset's weight is scaled by (1 - sev[t]) so a
    detected regime break de-risks that asset.
    """
    close = np.asarray(close, float)
    T, N = close.shape
    warm = max(lookbacks)
    ret = np.zeros((T, N)); ret[1:] = close[1:] / close[:-1] - 1.0
    W = np.zeros((T, N)); cur = np.zeros(N)
    for t in range(warm, T):
        if (t - warm) % rebal == 0:
            sig = np.mean([np.sign(close[t] / close[t - lb] - 1.0) for lb in lookbacks], axis=0)
            vol = np.std(ret[t - vol_win:t], axis=0) + 1e-9
            w = sig * target / vol
            w = w / (np.sum(np.abs(w)) + 1e-9)
            if gate and sev is not None:
                w = w * (1.0 - sev[t])
            cur = w
        W[t] = cur
    return W
