"""Realistic cost model: bid/ask spread on turnover + overnight short financing
(eToro CFD reality). Inputs are aligned (M,N) weight and next-day return matrices."""
from __future__ import annotations
import numpy as np


def net_returns(weights, fwd_ret, spread_bps=5.0, short_fin_bps_annual=300.0):
    weights = np.asarray(weights, float)
    fwd_ret = np.asarray(fwd_ret, float)
    gross = np.nansum(weights * fwd_ret, axis=1)

    turn = np.empty(len(weights))
    turn[0] = np.nansum(np.abs(weights[0]))
    if len(weights) > 1:
        turn[1:] = np.nansum(np.abs(weights[1:] - weights[:-1]), axis=1)
    tc = (spread_bps / 1e4) * turn

    short_notional = np.nansum(np.clip(-weights, 0.0, None), axis=1)
    fin = (short_fin_bps_annual / 1e4 / 252.0) * short_notional
    return gross - tc - fin
