"""Bayesian Online Changepoint Detection (Adams & MacKay 2007), constant hazard,
Gaussian predictive with a Normal-Normal conjugate prior on the run mean and a
fixed observation variance sigma2. Returns per-step break severity = posterior
mass on short run lengths P(r_t < kshort) — this rises sharply after a regime break
(the run-length mass collapses to small r). NOTE: the normalized P(r_t = 0) is NOT a
usable detector — it equals the hazard at every step by construction; the collapse of
mass onto short run lengths is what carries the changepoint signal."""
from __future__ import annotations
import numpy as np


def bocpd_gaussian(x, hazard=1/250.0, mu0=0.0, kappa0=1.0, sigma2=1.0, rmax=300, kshort=5):
    x = np.asarray(x, dtype=float)
    T = len(x)
    R = np.zeros(rmax + 1); R[0] = 1.0       # run-length posterior
    sums = np.zeros(rmax + 1)                 # sum of obs in each run
    counts = np.zeros(rmax + 1)               # count of obs in each run
    severity = np.zeros(T)

    for t in range(T):
        post_prec = 1.0 / kappa0 + counts / sigma2
        post_mean = (mu0 / kappa0 + sums / sigma2) / post_prec
        pred_var = sigma2 + 1.0 / post_prec
        pred = np.exp(-0.5 * (x[t] - post_mean) ** 2 / pred_var) / np.sqrt(2 * np.pi * pred_var)

        growth = R * pred * (1.0 - hazard)
        cp = np.sum(R * pred * hazard)
        newR = np.zeros(rmax + 1)
        newR[1:] = growth[:-1]
        newR[0] = cp
        newR /= (newR.sum() + 1e-300)
        R = newR
        severity[t] = R[:kshort].sum()       # mass on short run lengths = break severity

        new_sums = np.zeros(rmax + 1); new_counts = np.zeros(rmax + 1)
        new_sums[1:] = sums[:-1] + x[t]
        new_counts[1:] = counts[:-1] + 1.0
        sums, counts = new_sums, new_counts

    return severity
