"""Parametric synthetic daily generator for pretraining the attention model. Produces N MUTUALLY
INDEPENDENT (uncorrelated) daily close series so the portfolio-Sharpe loss gets perfect diversity
(ENB ~ N) plus unlimited 'time' -- the two things attention lacked on real data. Parametric (NOT
bootstrapped from real prices) => no leakage of the real OOS. 'structured' = a per-series random mix
of trend / mean-reversion / vol-clustering / jumps; 'randomwalk' = pure GBM, no signal (the honesty
control)."""
from __future__ import annotations
import numpy as np
import pandas as pd

BUSINESS_START = "2000-01-03"


def _series_structured(rng, T):
    """One independent daily return series: regime-switching mix of drift (trend), mean-reversion,
    GARCH-like vol clustering, and occasional jumps. Returns (T,) simple returns."""
    r = np.zeros(T)
    w, a, b = 1e-5, 0.08, 0.90
    sig2 = w / (1 - a - b)
    level = 0.0
    t = 0
    while t < T:
        seglen = int(rng.integers(20, 120))
        mode = rng.choice(["trend", "mr", "flat"], p=[0.4, 0.4, 0.2])
        drift = float(rng.normal(0, 4e-4)) if mode == "trend" else 0.0
        kappa = float(rng.uniform(0.02, 0.10)) if mode == "mr" else 0.0
        for _ in range(seglen):
            if t >= T:
                break
            if t > 0:
                sig2 = w + a * r[t - 1] ** 2 + b * sig2
            eps = float(rng.normal(0, np.sqrt(sig2)))
            r[t] = drift - kappa * level + eps
            if rng.random() < 0.01:
                r[t] += float(rng.normal(0, 0.05))
            level += r[t]
            t += 1
    return r


def _series_randomwalk(rng, T):
    """Pure GBM returns, ~zero drift, constant vol -> NO learnable signal (honesty control)."""
    return rng.normal(0.0, 0.01, T)


def make_synthetic(kind="structured", n_assets=18, T=6000, seed=0):
    """Return a (T, n_assets) DataFrame of INDEPENDENT synthetic daily closes (each starts at 100).
    kind in {"structured", "randomwalk"}. Deterministic in `seed`."""
    rng = np.random.default_rng(seed)
    gen = _series_structured if kind == "structured" else _series_randomwalk
    cols = {}
    for j in range(n_assets):
        r = gen(rng, T)
        cols[f"S{j:02d}"] = 100.0 * np.cumprod(1.0 + r)
    idx = pd.bdate_range(BUSINESS_START, periods=T)
    return pd.DataFrame(cols, index=idx)
