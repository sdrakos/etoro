"""Position-sizing and capital-allocation strategies (standalone, reusable, no IO).

Implements the levers from the position-sizing literature, usable independently of paper4:
  - inverse_vol_weights        : risk-parity-flavored (Roncalli)
  - min_variance_weights       : Markowitz minimum-variance (long-only, normalized)
  - hrp_weights                : Hierarchical Risk Parity (Lopez de Prado 2016)
  - ledoit_wolf_cov            : shrinkage covariance (Ledoit & Wolf 2004)
  - kelly_leverage             : (fractional) Kelly growth-optimal leverage (Kelly 1956; Thorp)

All allocation functions take a covariance matrix and return long-only risk-budget weights that
sum to 1 (use them as position MAGNITUDES, multiplied by a trend sign for a directional book).
"""
from __future__ import annotations
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def ledoit_wolf_cov(returns):
    """Ledoit-Wolf shrunk covariance from a (W, N) window of returns."""
    from sklearn.covariance import LedoitWolf
    return LedoitWolf().fit(np.asarray(returns, float)).covariance_


def inverse_vol_weights(cov):
    """w_i proportional to 1/sigma_i, normalized to sum 1 (equal-risk if uncorrelated)."""
    sig = np.sqrt(np.diag(np.asarray(cov, float)))
    w = 1.0 / (sig + 1e-12)
    return w / w.sum()


def min_variance_weights(cov):
    """Long-only minimum-variance: w ∝ Σ^{-1}1, negatives clipped, normalized."""
    cov = np.asarray(cov, float)
    inv = np.linalg.pinv(cov) @ np.ones(cov.shape[0])
    inv = np.clip(inv, 0.0, None)
    s = inv.sum()
    return inv / s if s > 0 else np.ones(cov.shape[0]) / cov.shape[0]


def _quasi_diag(link, n):
    """Leaf order from a scipy linkage tree (quasi-diagonalization)."""
    def expand(node):
        if node < n:
            return [int(node)]
        l, r = int(link[node - n, 0]), int(link[node - n, 1])
        return expand(l) + expand(r)
    return expand(2 * n - 2)


def _cluster_var(cov, items):
    c = cov[np.ix_(items, items)]
    ivp = 1.0 / np.diag(c); ivp /= ivp.sum()
    return float(ivp @ c @ ivp)


def hrp_weights(cov):
    """Hierarchical Risk Parity (Lopez de Prado 2016): tree-clustered inverse-variance
    allocation, robust to covariance estimation error (no matrix inversion)."""
    cov = np.asarray(cov, float); n = cov.shape[0]
    if n == 1:
        return np.array([1.0])
    std = np.sqrt(np.diag(cov))
    corr = np.clip(cov / np.outer(std, std), -1.0, 1.0)
    dist = np.sqrt((1.0 - corr) / 2.0)
    link = linkage(squareform(dist, checks=False), method="single")
    order = _quasi_diag(link, n)
    w = {i: 1.0 for i in order}
    clusters = [list(order)]
    while clusters:
        nxt = []
        for c in clusters:
            if len(c) > 1:
                half = len(c) // 2
                c0, c1 = c[:half], c[half:]
                v0, v1 = _cluster_var(cov, c0), _cluster_var(cov, c1)
                alpha = 1.0 - v0 / (v0 + v1)
                for i in c0:
                    w[i] *= alpha
                for i in c1:
                    w[i] *= (1.0 - alpha)
                nxt += [c0, c1]
        clusters = nxt
    return np.array([w[i] for i in range(n)])


def kelly_leverage(returns, fraction=1.0, cap=3.0):
    """(Fractional) Kelly growth-optimal leverage for a single return stream:
    f* = mean/variance; scaled by `fraction` and clipped to [0, cap]. Quarter/half Kelly
    (fraction=0.25/0.5) is the standard risk-aware choice; full Kelly over-bets."""
    r = np.asarray(returns, float)
    f = r.mean() / (r.var() + 1e-12)
    return float(np.clip(fraction * f, 0.0, cap))


def realized_vol(returns, method="rolling", halflife=21, periods=252):
    """Annualized realized volatility of a 1-D daily return stream.
    method="rolling": plain standard deviation of the whole window (equal weight).
    method="ewma":    exponentially-weighted std (recent days weigh more -> faster reaction);
                      `halflife` in days controls how fast old days fade."""
    r = np.asarray(returns, float)
    if method == "ewma":
        lam = 0.5 ** (1.0 / halflife)
        w = lam ** np.arange(len(r) - 1, -1, -1)          # newest day -> largest weight
        w = w / (w.sum() + 1e-12)
        var = float(np.sum(w * (r - np.sum(w * r)) ** 2))
        return float(np.sqrt(var) * np.sqrt(periods))
    return float(r.std() * np.sqrt(periods))
