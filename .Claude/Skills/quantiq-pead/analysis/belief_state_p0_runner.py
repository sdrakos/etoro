#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
belief_state_p0_runner.py
=========================
P0 walk-forward evaluation for:
  "Belief-State RL for Cross-Sectional Equity Selection" — Section 9.2.

Central pre-registered hypothesis (Section 8):
  belief-state features beat raw-price features, out-of-sample, net of costs,
  in a dollar-neutral cross-sectional ranking task; reject if the belief arm
  does not exceed the raw arm in information ratio by a margin, or if its IR < ~0.4.

What this script produces (the six §9.2 deliverables):
  (1) headline OOS information ratio with a (bootstrap) confidence interval
  (2) the raw-vs-belief ablation gap with a significance test
  (3) equity curve and drawdown vs. buy-and-hold
  (4) realized beta (confirming market-neutrality)
  (5) rank-IC time series and its (Newey-West) t-statistic
  (6) sensitivity to costs and to (lambda, H)

DATA: by default this runs on a *synthetic* cross-sectional market with a known
weak, filterable signal — this is HARNESS VALIDATION (a la §9.1), NOT a market
result. To produce the real §9.2 number, replace load_panel() with real adjusted
prices (a yfinance loader is provided but guarded; it needs network access that
the research sandbox does not have).

Design choices (deliberately conservative, per the DER paper's overfitting lesson):
  * low-capacity LINEAR ranking policy, fit by ridge on each train fold only;
  * identical learner for belief and raw arms => fair ablation;
  * strict walk-forward with an H-day embargo; scaling+weights frozen before test;
  * score-weighted dollar-neutral portfolio (smooth, beta~0 by construction).
A DSR-gradient-trained policy is a drop-in replacement for fit_weights() if desired.

Author: Stefanos Drakos / AGEL AI.  Seed-deterministic.
"""

import json
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

RNG = np.random.default_rng(2025)

# ----------------------------------------------------------------------------
# 1. DATA
# ----------------------------------------------------------------------------
def make_synthetic_panel(n_assets=120, n_days=6000, lvl_noise=0.010,
                         vel_std=0.0008, regime=True, seed=2025):
    """
    Synthetic cross-sectional market matched to the paper's §4 model:
        latent:   l_t = l_{t-1} + v_{t-1} + eta_l,   v_t = v_{t-1} + eta_v
        observed: y_t = l_t + eps_t,   eps_t ~ N(0, lvl_noise^2)   (iid LEVEL noise)
    You trade at observed prices and earn observed returns dy_t = dl_t + deps_t.
    The predictable part of next return is the latent drift v_{t-1}; the differenced
    observation noise deps_t is large and unpredictable. Best-possible cross-sectional
    IC ~ sigma_v / sigma_(dy) ~ 0.0008/0.014 ~ 0.05 (paper's 0.02-0.05 range).
    Because the latent LEVEL is smooth and the noise is iid on the level, the Kalman
    filter is WELL-SPECIFIED and recovers v_t far better than raw differenced prices,
    so the belief arm should beat the raw arm. Regimes scale the observation noise.
    """
    rng = np.random.default_rng(seed)
    kappa = 0.04                                   # slow mean-reversion of drift
    q_v = (vel_std * np.sqrt(1 - (1 - kappa) ** 2))
    q_l = 0.0010                                   # small level innovation

    v = np.zeros((n_days, n_assets)); l = np.zeros((n_days, n_assets))
    v[0] = rng.normal(0, vel_std, n_assets)
    l[0] = rng.normal(0, 0.05, n_assets)
    for t in range(1, n_days):
        v[t] = (1 - kappa) * v[t-1] + rng.normal(0, q_v, n_assets)
        l[t] = l[t-1] + v[t-1] + rng.normal(0, q_l, n_assets)

    reg = np.ones(n_days)
    if regime:
        t = 0
        while t < n_days:
            length = rng.integers(150, 500)
            reg[t:t+length] = rng.choice([0.7, 1.0, 1.0, 1.8])
            t += length

    eps = rng.normal(0, 1.0, (n_days, n_assets)) * (lvl_noise * reg[:, None])
    common = np.cumsum(rng.normal(0, 0.005, n_days))[:, None]   # market level
    y = l + eps + common                                        # observed log-price

    prices = 100.0 * np.exp(y - y[0])
    dates = pd.bdate_range("2001-01-01", periods=n_days)
    cols = [f"A{i:03d}" for i in range(n_assets)]
    return pd.DataFrame(prices, index=dates, columns=cols)


def load_yfinance(tickers, start="2000-01-01", end="2024-12-31"):
    """REAL-DATA PATH (run on a machine with network). Returns adj-close panel."""
    import yfinance as yf  # noqa
    df = yf.download(tickers, start=start, end=end, auto_adjust=True,
                     progress=False)["Close"]
    return df.dropna(how="all").ffill().dropna(axis=1)


def load_panel():
    """Swap this for load_yfinance(my_universe) or load_csv(path) on your machine."""
    return make_synthetic_panel()


# ----------------------------------------------------------------------------
# 2. KALMAN LOCAL-LINEAR-TREND FILTER  ->  BELIEF FEATURES   (Appendix A)
# ----------------------------------------------------------------------------
def kalman_llt_features(logp, q_level=1e-6, q_vel=5e-8, r_obs=1e-4, lam=1.0):
    """
    Vectorized local-linear-trend Kalman filter across assets.
    logp: (T, N) log prices.  Returns dict of (T, N) belief features:
       v_hat (trend velocity), v_tstat (v/sqrt(Pvv)),
       level_gap (y - level_hat), innov_z (standardized innovation).
    'lam' is an optional forgetting factor inflating process noise (online adapt).
    """
    T, N = logp.shape
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q0 = np.array([[q_level, 0.0], [0.0, q_vel]]) / max(lam, 1e-6)
    R = r_obs

    x = np.zeros((N, 2)); x[:, 0] = logp[0]
    P = np.tile(np.array([[1e-2, 0.0], [0.0, 1e-4]]), (N, 1, 1))

    v_hat = np.full((T, N), np.nan); v_tstat = np.full((T, N), np.nan)
    level_gap = np.full((T, N), np.nan); innov_z = np.full((T, N), np.nan)

    for t in range(1, T):
        x = x @ F.T                                   # predict state
        P = F @ P @ F.T + Q0                           # predict cov
        lvl_pred = x[:, 0]
        S = P[:, 0, 0] + R                             # innovation variance
        nu = logp[t] - lvl_pred                        # innovation
        K0 = P[:, 0, 0] / S; K1 = P[:, 1, 0] / S       # Kalman gain
        x[:, 0] += K0 * nu; x[:, 1] += K1 * nu         # update
        P[:, 0, 0] -= K0 * P[:, 0, 0]; P[:, 0, 1] -= K0 * P[:, 0, 1]
        P[:, 1, 0] -= K1 * P[:, 0, 0]; P[:, 1, 1] -= K1 * P[:, 0, 1]

        v_hat[t] = x[:, 1]
        v_tstat[t] = x[:, 1] / np.sqrt(np.maximum(P[:, 1, 1], 1e-18))
        level_gap[t] = logp[t] - x[:, 0]
        innov_z[t] = nu / np.sqrt(np.maximum(S, 1e-18))

    return {"v_hat": v_hat, "v_tstat": v_tstat,
            "level_gap": level_gap, "innov_z": innov_z}


def raw_features(logp):
    """Ablation arm: raw price-window features of comparable dimension (k-day returns)."""
    T, N = logp.shape
    feats = {}
    for k in (5, 20, 60):
        f = np.full((T, N), np.nan)
        f[k:] = logp[k:] - logp[:-k]
        feats[f"ret_{k}"] = f
    # price z-score over 60d (mean-reversion-ish raw feature)
    f = np.full((T, N), np.nan)
    for t in range(60, T):
        w = logp[t-60:t]
        f[t] = (logp[t] - w.mean(0)) / (w.std(0) + 1e-9)
    feats["pz_60"] = f
    return feats


# ----------------------------------------------------------------------------
# 3. POLICY  (low-capacity linear ranker, ridge-fit on train fold only)
# ----------------------------------------------------------------------------
def xs_standardize(M):
    """Cross-sectional (per-row) standardization, ignoring NaNs."""
    mu = np.nanmean(M, axis=1, keepdims=True)
    sd = np.nanstd(M, axis=1, keepdims=True) + 1e-12
    Z = (M - mu) / sd
    return np.nan_to_num(Z, nan=0.0)


def stack_features(feat_dict):
    """-> X of shape (T, N, d) cross-sectionally standardized per feature."""
    keys = sorted(feat_dict)
    return np.stack([xs_standardize(feat_dict[k]) for k in keys], axis=-1), keys


def fit_weights(X_tr, fwd_tr, ridge=5.0):
    """Ridge of cross-sectionally-demeaned forward returns on stacked features."""
    d = X_tr.shape[-1]
    Xf = X_tr.reshape(-1, d)
    yf = (fwd_tr - np.nanmean(fwd_tr, axis=1, keepdims=True)).reshape(-1)
    m = np.isfinite(yf)
    Xf, yf = Xf[m], yf[m]
    A = Xf.T @ Xf + ridge * np.eye(d)
    return np.linalg.solve(A, Xf.T @ yf)


def portfolio_returns(X, w, fwd, cost_bps):
    """
    Score-weighted dollar-neutral portfolio.
    score = X.w (already xs-standardized); weights = xs-standardized score,
    L1-normalized to gross 1 => sum~0 (dollar-neutral), beta~0 by construction.
    Returns (R_t net of costs, weights, daily rank-IC).
    """
    T = X.shape[0]
    score = X @ w
    score = xs_standardize(score)
    gross = np.nansum(np.abs(score), axis=1, keepdims=True) + 1e-12
    W = score / gross
    R = np.full(T, np.nan); ric = np.full(T, np.nan)
    prevW = np.zeros(W.shape[1])
    cost = cost_bps * 1e-4
    for t in range(T):
        if not np.isfinite(fwd[t]).any():
            continue
        turn = np.nansum(np.abs(W[t] - prevW))
        R[t] = np.nansum(W[t] * np.nan_to_num(fwd[t])) - cost * turn
        prevW = W[t]
        # cross-sectional rank-IC of score vs forward demeaned return
        fr = fwd[t] - np.nanmean(fwd[t])
        a, b = score[t], fr
        mm = np.isfinite(a) & np.isfinite(b)
        if mm.sum() > 10:
            ra = pd.Series(a[mm]).rank().values
            rb = pd.Series(b[mm]).rank().values
            ric[t] = np.corrcoef(ra, rb)[0, 1]
    return R, W, ric


# ----------------------------------------------------------------------------
# 4. METRICS
# ----------------------------------------------------------------------------
def ann_ir(R):
    R = R[np.isfinite(R)]
    if R.std() == 0 or len(R) < 2:
        return 0.0
    return np.sqrt(252) * R.mean() / R.std()


def max_drawdown(R):
    eq = np.cumprod(1 + np.nan_to_num(R))
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1).min())


def newey_west_t(x, L=10):
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 5:
        return 0.0
    xm = x - x.mean()
    g0 = (xm @ xm) / n
    var = g0
    for k in range(1, L + 1):
        gk = (xm[k:] @ xm[:-k]) / n
        var += 2 * (1 - k / (L + 1)) * gk
    se = np.sqrt(var / n)
    return float(x.mean() / se) if se > 0 else 0.0


def realized_beta(R, mkt):
    m = np.isfinite(R) & np.isfinite(mkt)
    if m.sum() < 5:
        return 0.0
    return float(np.cov(R[m], mkt[m])[0, 1] / (np.var(mkt[m]) + 1e-18))


def bootstrap_ir_ci(R, n=2000, seed=2025):
    R = R[np.isfinite(R)]
    rng = np.random.default_rng(seed)
    irs = [ann_ir(R[rng.integers(0, len(R), len(R))]) for _ in range(n)]
    return float(np.percentile(irs, 2.5)), float(np.percentile(irs, 97.5))


# ----------------------------------------------------------------------------
# 5. WALK-FORWARD ENGINE
# ----------------------------------------------------------------------------
def walk_forward(prices, arm="belief", train=1000, test=252, embargo=10,
                 cost_bps=5.0, lam=1.0, ridge=5.0):
    logp = np.log(prices.values)
    fwd = np.full_like(logp, np.nan)
    # T+1 implementation lag: decide at t, trade at t+1, earn t+1 -> t+2.
    # This avoids trading against the same-day observation noise (bid-ask bounce).
    fwd[:-2] = logp[2:] - logp[1:-1]

    if arm == "belief":
        feats = kalman_llt_features(logp, lam=lam)
    elif arm == "raw":
        feats = raw_features(logp)
    else:
        raise ValueError(arm)
    X, _ = stack_features(feats)

    T = logp.shape[0]
    R_all = np.full(T, np.nan); ric_all = np.full(T, np.nan)
    start = train + 100                         # warmup for features
    s = start
    while s + test <= T:
        tr0, tr1 = s - train, s - embargo
        w = fit_weights(X[tr0:tr1], fwd[tr0:tr1], ridge=ridge)
        te0, te1 = s, s + test
        R, _, ric = portfolio_returns(X[te0:te1], w, fwd[te0:te1], cost_bps)
        R_all[te0:te1] = R; ric_all[te0:te1] = ric
        s += test
    return R_all, ric_all


def market_return(prices):
    r = np.log(prices.values[1:]) - np.log(prices.values[:-1])
    m = np.full(prices.shape[0], np.nan)
    m[1:] = np.nanmean(r, axis=1)
    return m


# ----------------------------------------------------------------------------
# 6. MAIN
# ----------------------------------------------------------------------------
def summarize(R, ric, mkt, label):
    lo, hi = bootstrap_ir_ci(R)
    return {
        "arm": label,
        "IR": round(ann_ir(R), 3),
        "IR_CI95": [round(lo, 3), round(hi, 3)],
        "Sharpe": round(ann_ir(R), 3),
        "MaxDD": round(max_drawdown(R), 3),
        "realized_beta": round(realized_beta(R, mkt), 4),
        "rankIC_mean": round(np.nanmean(ric), 4),
        "rankIC_t_NW": round(newey_west_t(ric), 2),
    }


def main():
    prices = load_panel()
    mkt = market_return(prices)
    print(f"# panel: {prices.shape[0]} days x {prices.shape[1]} assets "
          f"({prices.index[0].date()}..{prices.index[-1].date()})\n")

    Rb, ricb = walk_forward(prices, "belief")
    Rr, ricr = walk_forward(prices, "raw")

    sb = summarize(Rb, ricb, mkt, "belief")
    sr = summarize(Rr, ricr, mkt, "raw")

    # (2) ablation gap + significance (paired t on daily OOS returns)
    m = np.isfinite(Rb) & np.isfinite(Rr)
    diff = Rb[m] - Rr[m]
    t_gap = np.sqrt(len(diff)) * diff.mean() / (diff.std() + 1e-18)
    gap = sb["IR"] - sr["IR"]

    # (6) sensitivity
    sens = []
    for c in (1.0, 5.0, 10.0):
        R, ric = walk_forward(prices, "belief", cost_bps=c)
        sens.append({"type": "cost_bps", "value": c, "belief_IR": round(ann_ir(R), 3)})
    for lam in (0.97, 0.99, 1.0):
        R, ric = walk_forward(prices, "belief", lam=lam)
        sens.append({"type": "lambda", "value": lam, "belief_IR": round(ann_ir(R), 3)})
    for H in (1, 10, 21):
        R, ric = walk_forward(prices, "belief", embargo=H)
        sens.append({"type": "embargo_H", "value": H, "belief_IR": round(ann_ir(R), 3)})

    # pre-registered falsification (Section 8)
    MARGIN, FLOOR = 0.10, 0.40
    supported = (gap >= MARGIN) and (sb["IR"] >= FLOOR)
    verdict = "SUPPORTED" if supported else "REJECTED (null/marginal)"

    out = {
        "headline": sb, "raw_arm": sr,
        "ablation": {"IR_gap_belief_minus_raw": round(gap, 3),
                     "paired_t_daily": round(float(t_gap), 2)},
        "falsification": {"margin": MARGIN, "floor": FLOOR, "verdict": verdict},
        "sensitivity": sens,
    }
    print(json.dumps(out, indent=2))

    # figures + arrays
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        idx = prices.index
        eb = np.cumprod(1 + np.nan_to_num(Rb)); er = np.cumprod(1 + np.nan_to_num(Rr))
        bh = np.cumprod(1 + np.nan_to_num(mkt))
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
        ax[0].plot(idx, eb, label=f"belief (IR {sb['IR']})", lw=1.3)
        ax[0].plot(idx, er, label=f"raw (IR {sr['IR']})", lw=1.0)
        ax[0].plot(idx, bh, "--", color="gray", lw=0.9, label="buy&hold")
        ax[0].set_title("OOS equity (dollar-neutral)"); ax[0].legend(); ax[0].set_yscale("log")
        rr = pd.Series(ricb, index=idx).rolling(63).mean()
        ax[1].plot(idx, rr, lw=1.0)
        ax[1].axhline(0, color="k", lw=0.6)
        ax[1].set_title(f"belief rank-IC (63d MA); NW t = {sb['rankIC_t_NW']}")
        plt.tight_layout(); plt.savefig("p0_results.png", dpi=110)
        print("\n# wrote p0_results.png")
    except Exception as e:
        print("plotting skipped:", e)

    with open("p0_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("# wrote p0_results.json")
    return out


if __name__ == "__main__":
    main()
