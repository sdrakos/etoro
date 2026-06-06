"""Per-asset feature tensor for the Deep Momentum Network.

From a (T,N) close matrix builds X (N,T,F) with F=10 features per asset/day:
 - 5 multi-horizon returns (1/21/63/126/252d), each normalised by realised vol;
 - log realised volatility (63d);
 - Kalman local-linear-trend belief: velocity, trend significance, standardised innovation;
 - BOCPD changepoint severity.
Also returns fwd (N,T): each asset's next-day return (the training target).
Features are clipped to [-10,10] and NaN-cleaned so they are safe to feed a network.
"""
from __future__ import annotations
import os, sys
import numpy as np

_STRAT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                      "Strategies", "slow-momentum-fast-reversion"))
if _STRAT not in sys.path:
    sys.path.insert(0, _STRAT)
from kalman_llt import kalman_llt          # noqa: E402
from bocpd import bocpd_gaussian           # noqa: E402

LOOKBACKS = (1, 21, 63, 126, 252)
VOL_WIN = 63


def build_features(close):
    close = np.asarray(close, float)
    T, N = close.shape
    ret = np.nan_to_num(np.vstack([np.zeros((1, N)), close[1:] / close[:-1] - 1.0]))

    rv = np.zeros((T, N))
    for t in range(VOL_WIN, T):
        rv[t] = np.std(ret[t - VOL_WIN:t], axis=0)
    rv = np.maximum(rv, 1e-3)

    feats = []
    for lb in LOOKBACKS:
        m = np.zeros((T, N))
        for t in range(lb, T):
            m[t] = close[t] / close[t - lb] - 1.0
        feats.append(m / (rv * np.sqrt(lb)))
    feats.append(np.log(rv))

    vel = np.zeros((T, N)); tsig = np.zeros((T, N)); sinn = np.zeros((T, N)); sev = np.zeros((T, N))
    for j in range(N):
        o = kalman_llt(np.log(np.maximum(close[:, j], 1e-9)))
        vel[:, j] = o["velocity"]; tsig[:, j] = o["trend_sig"]; sinn[:, j] = o["std_innov"]
        sev[:, j] = bocpd_gaussian(ret[:, j], hazard=1 / 250.0,
                                   sigma2=float(np.var(ret[1:, j]) + 1e-12))
    feats += [vel * 100, np.clip(tsig, -5, 5), np.clip(sinn, -5, 5), sev]

    X = np.transpose(np.stack(feats, axis=2), (1, 0, 2))       # (N,T,F)
    X = np.nan_to_num(np.clip(X, -10, 10), nan=0.0, posinf=10, neginf=-10)
    fwd = np.zeros((N, T)); fwd[:, :-1] = ret[1:].T
    return X, fwd
