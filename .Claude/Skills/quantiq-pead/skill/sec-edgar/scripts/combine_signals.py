#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
combine_signals.py — merge several weak, orthogonal signals into ONE score by RISK PARITY.

The edge is not one strong signal; it is many weak, uncorrelated ones combined so each
contributes EQUAL RISK (not equal capital). A noisy signal gets a smaller weight, a steady
one a larger weight — automatically, by formula, with nothing "learned" (so no overfitting).

Inputs: a dict of cross-sectional signal frames, each a (date x ticker) DataFrame
        (e.g. {"own_pead": pead_signal, "peer_leadlag": leadlag_signal, ...}).
Each is z-scored cross-sectionally per day, then weighted and summed into a final
(date x ticker) score you can rank and trade.

Weighting modes:
  "inverse_vol" : w_i ∝ 1/σ_i        (simple risk parity; ignores correlation)
  "erc"         : equal risk contribution (accounts for correlation between signals)
  "equal"       : plain average (baseline)

σ_i is the volatility of signal i's own long-short portfolio. If you pass `returns`
(a date x ticker frame of next-day returns) the vols/correlations are computed from the
real signal portfolios. Without returns, a scale proxy (dispersion of the signal) is used.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
def zscore_xs(frame):
    """Cross-sectionally standardize each row (day): mean 0, std 1 across tickers."""
    mu = frame.mean(axis=1)
    sd = frame.std(axis=1).replace(0, np.nan)
    return frame.sub(mu, axis=0).div(sd, axis=0).fillna(0.0)


def signal_portfolio_returns(signal, returns):
    """Daily long-short return of one signal: weight by z-score, dollar-neutral,
    earn next-day return. Used to measure each signal's risk for weighting."""
    z = zscore_xs(signal)
    common_c = z.columns.intersection(returns.columns)
    z = z[common_c]; r = returns[common_c].reindex(z.index)
    w = z.div(z.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    return (w.shift(1) * r).sum(axis=1)        # shift(1): trade on next day's return


# ---------------------------------------------------------------------------
def inverse_vol_weights(vols):
    inv = 1.0 / vols.replace(0, np.nan)
    return (inv / inv.sum()).fillna(0.0)


def erc_weights(cov, iters=200, tol=1e-10):
    """Equal Risk Contribution weights via the simple fixed-point iteration
    w_i <- w_i / (Σw)_i, renormalized. Converges to equal risk contributions."""
    n = cov.shape[0]
    w = np.ones(n) / n
    C = cov.values if hasattr(cov, "values") else np.asarray(cov)
    for _ in range(iters):
        m = C @ w
        m[m == 0] = 1e-12
        w_new = w / m
        w_new = np.clip(w_new, 0, None)
        s = w_new.sum()
        w_new = w_new / s if s > 0 else np.ones(n) / n
        if np.max(np.abs(w_new - w)) < tol:
            w = w_new; break
        w = w_new
    return pd.Series(w, index=(cov.index if hasattr(cov, "index") else None))


# ---------------------------------------------------------------------------
def combine(signal_frames, returns=None, method="inverse_vol"):
    """
    Combine a dict of (date x ticker) signal frames into one final score frame.

    method: "inverse_vol" (default), "erc", or "equal".
    returns: optional (date x ticker) NEXT-DAY returns to measure real signal risk.
    Returns: (combined_signal_frame, weights_Series).
    """
    names = list(signal_frames)
    # align all signals to a common index/columns
    idx = None; cols = None
    for f in signal_frames.values():
        idx = f.index if idx is None else idx.union(f.index)
        cols = f.columns if cols is None else cols.union(f.columns)
    Z = {k: zscore_xs(signal_frames[k].reindex(index=idx, columns=cols).fillna(0.0))
         for k in names}

    if method == "equal":
        w = pd.Series(1.0 / len(names), index=names)
    elif returns is not None:
        # real risk: build each signal's portfolio return series
        port = pd.DataFrame({k: signal_portfolio_returns(signal_frames[k], returns)
                             for k in names}).dropna()
        if method == "erc":
            w = erc_weights(port.cov()); w.index = names
        else:
            w = inverse_vol_weights(port.std())
    else:
        # no returns: use temporal volatility of each signal's cross-sectional dispersion
        disp = pd.Series({k: Z[k].abs().mean(axis=1).std() for k in names})
        w = inverse_vol_weights(disp)

    combined = sum(w[k] * Z[k] for k in names)
    return combined, w


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # tiny self-contained demo: two signals, peer steadier than own
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2022-01-01", periods=400)
    tks = [f"T{i}" for i in range(30)]
    truth = pd.DataFrame(rng.normal(size=(len(days), len(tks))), index=days, columns=tks)
    own = truth + rng.normal(0, 2.0, truth.shape)     # noisy view of truth
    peer = truth + rng.normal(0, 1.0, truth.shape)    # steadier view
    rets = (truth.shift(-1) * 0.01 + rng.normal(0, 0.01, truth.shape))
    comb, w = combine({"own": own, "peer": peer}, returns=rets, method="inverse_vol")
    print("weights (inverse-vol):"); print(w.round(3).to_string())
    comb_e, we = combine({"own": own, "peer": peer}, returns=rets, method="erc")
    print("\nweights (ERC):"); print(we.round(3).to_string())
    print("\ncombined shape:", comb.shape)
