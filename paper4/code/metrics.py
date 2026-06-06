"""Honest performance metrics: annualized IR, max drawdown, Newey-West t-stat,
Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014), and durability by year."""
from __future__ import annotations
import numpy as np
from datetime import datetime, timezone
from math import erf, sqrt


def ann_ir(r, periods=252):
    r = np.asarray(r, float)
    return r.mean() / (r.std() + 1e-12) * np.sqrt(periods)


def max_drawdown(r):
    eq = np.cumprod(1.0 + np.asarray(r, float))
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1.0).min())


def newey_west_t(r, lag=21):
    r = np.asarray(r, float); n = len(r); e = r - r.mean()
    s = np.mean(e * e)
    for l in range(1, lag + 1):
        cov = np.mean(e[l:] * e[:-l])
        s += 2.0 * (1.0 - l / (lag + 1.0)) * cov
    se = np.sqrt(max(s, 1e-18) / n)
    return float(r.mean() / (se + 1e-18))


def _norm_cdf(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _inv_norm(p):
    # Acklam's rational approximation to the inverse normal CDF
    p = min(max(p, 1e-9), 1 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = sqrt(-2 * np.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = sqrt(-2 * np.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def deflated_sharpe(r, n_trials=1, periods=252):
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014). Per-observation SR vs an
    expected-maximum benchmark from n_trials, scaled by the SR estimation standard error
    (skew/kurtosis adjusted). Returns prob in [0,1]; monotonically decreasing in n_trials."""
    r = np.asarray(r, float); n = len(r)
    mu, sd = r.mean(), r.std() + 1e-12
    sr = mu / sd                                   # per-observation Sharpe
    g3 = np.mean(((r - mu) / sd) ** 3)
    g4 = np.mean(((r - mu) / sd) ** 4)
    se_sr = np.sqrt(max(1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2, 1e-9) / max(n - 1, 1))
    euler = 0.5772156649
    if n_trials > 1:
        emax = ((1 - euler) * _inv_norm(1 - 1.0 / n_trials)
                + euler * _inv_norm(1 - 1.0 / (n_trials * np.e)))
    else:
        emax = 0.0
    sr0 = se_sr * emax
    return float(_norm_cdf((sr - sr0) / se_sr))


def durability_by_year(r, dates_ms, periods=252):
    r = np.asarray(r, float)
    years = np.array([datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).year for ms in dates_ms])
    out = {}
    for y in np.unique(years):
        rr = r[years == y]
        if len(rr) > 20:
            out[int(y)] = round(ann_ir(rr, periods), 3)
    return out
