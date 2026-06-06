"""Walk-forward runner: per-asset belief states -> variant weights -> costed returns -> metrics.
Source of truth for the paper's numbers. Pure-numpy; data is injected as a (T,N) close matrix."""
from __future__ import annotations
import os, sys
import numpy as np

# make the strategy package importable
_STRAT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                      "Strategies", "slow-momentum-fast-reversion"))
if _STRAT not in sys.path:
    sys.path.insert(0, _STRAT)

from kalman_llt import kalman_llt          # noqa: E402
from bocpd import bocpd_gaussian           # noqa: E402
from signals import build_weights          # noqa: E402
from costs import net_returns              # noqa: E402
from metrics import ann_ir, max_drawdown, newey_west_t, deflated_sharpe  # noqa: E402


def per_asset_states(close, sigma2=None):
    """Apply Kalman LLT + BOCPD to each column. Returns (velocity, trend_sig, severity) (T,N)."""
    T, N = close.shape
    vel = np.zeros((T, N)); sig = np.zeros((T, N)); sev = np.zeros((T, N))
    logc = np.log(np.maximum(close, 1e-9))
    rets = np.zeros((T, N)); rets[1:] = logc[1:] - logc[:-1]
    for j in range(N):
        if not np.isfinite(logc[:, j]).all():
            continue
        out = kalman_llt(logc[:, j])
        vel[:, j] = out["velocity"]
        sig[:, j] = out["trend_sig"]
        s2 = sigma2 if sigma2 is not None else (np.var(rets[1:, j]) + 1e-9)
        sev[:, j] = bocpd_gaussian(rets[:, j], hazard=1 / 250.0, sigma2=s2)
    return vel, sig, sev


def forward_returns(close):
    T, N = close.shape
    fwd = np.zeros((T, N))
    fwd[:-1] = close[1:] / close[:-1] - 1.0
    return fwd


def run_variant(variant, close, k=10, warmup=252, embargo=21,
                spread_bps=5.0, short_fin_bps_annual=300.0, n_trials=3):
    vel, sig, sev = per_asset_states(close)
    W = build_weights(variant, close, vel, sig, sev, k=k, warmup=warmup)
    if embargo > 0:
        W[-embargo:] = 0.0                 # embargo tail (no test bar bleeds past data end)
    fwd = forward_returns(close)
    net = net_returns(W, fwd, spread_bps=spread_bps, short_fin_bps_annual=short_fin_bps_annual)
    active = net[warmup:len(net) - embargo] if embargo > 0 else net[warmup:]
    return {
        "variant": variant, "weights": W, "net": net,
        "ir": ann_ir(active), "max_dd": max_drawdown(active),
        "nw_t": newey_west_t(active, lag=21),
        "dsr": deflated_sharpe(active, n_trials=n_trials),
        "turnover": float(np.nansum(np.abs(np.diff(W, axis=0))) / max(len(W), 1)),
    }
