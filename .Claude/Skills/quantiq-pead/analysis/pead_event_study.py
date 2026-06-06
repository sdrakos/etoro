#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pead_event_study.py
===================
The rigorous way to do PEAD: instead of assuming "hold 60 days", MEASURE the
drift day-by-day after the announcement, fit its decay, and check how the whole
effect fades across the years.

Inputs (swap in real data on your machine):
  events : DataFrame [ticker, ann_date, sue]   (from the sec-edgar skill: compute_sue)
  prices : DataFrame  (index = trading days, columns = tickers)  adjusted close

Outputs (the four things you asked for):
  (1) drift profile b(k): abnormal return on day k after entry, per unit SUE
      + cumulative B(h), with EVENT/Newey-West-aware inference via the
      calendar-time portfolio (handles overlap + earnings-season clustering).
  (2) decay: exponential fit of b(k) -> half-life, and optimal holding horizon h*.
  (3) cross-time decay (durability): the tradable IR per calendar year + trend.
  (4) SUE persistence (the legitimate forward-looking nugget, Bernard-Thomas):
      corr(SUE_t, SUE_{t+1}) within ticker.

Entry uses a strict T+1 lag (position formed the first trading day AFTER the
announcement). Returns are abnormal = cross-sectionally demeaned (market-neutral).

By default runs on SYNTHETIC data with a KNOWN half-life and a KNOWN yearly fade,
to validate the estimator recovers the truth. This is harness validation, not a
market result.
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(2025)


# ---------------------------------------------------------------------------
# SYNTHETIC DATA with known truth (true half-life ~ tau*ln2, fading yearly)
# ---------------------------------------------------------------------------
def make_synthetic_pead(n_tickers=200, start="2010-01-01", end="2024-12-31",
                        tau=15.0, alpha0=0.0011, alpha_end=0.0003,
                        sue_rho=0.30, hold=60, seed=2025):
    """
    Build (prices, events) where each announcement injects a drift
        AR_k = alpha(year) * z_sue * exp(-k/tau)   for k = 0..hold-1
    decaying with timescale tau (=> half-life tau*ln2 ~ 10.4d for tau=15), and the
    strength alpha(year) fades linearly from alpha0 (start) to alpha_end (end).
    SUE follows an AR(1) per ticker (coef sue_rho) so the persistence test has a target.
    """
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range(start, end)
    T = len(cal); year = cal.year.values
    yr_frac = (year - year.min()) / (year.max() - year.min())
    alpha_t = alpha0 + (alpha_end - alpha0) * yr_frac          # per-day index

    tickers = [f"S{i:03d}" for i in range(n_tickers)]
    ret = rng.normal(0, 0.015, (T, n_tickers))                 # idiosyncratic
    ret += rng.normal(0, 0.008, (T, 1))                        # common market factor

    ev_rows = []
    for j, tk in enumerate(tickers):
        # quarterly events ~ every 63 trading days, clustered near quarter starts
        t = rng.integers(20, 60)
        prev_sue = rng.normal()
        while t < T - hold - 2:
            z = sue_rho * prev_sue + np.sqrt(1 - sue_rho**2) * rng.normal()
            prev_sue = z
            ann_idx = t
            entry = ann_idx + 1                                # T+1
            a = alpha_t[entry]
            ks = np.arange(hold)
            ret[entry:entry+hold, j] += a * z * np.exp(-ks / tau)
            ev_rows.append({"ticker": tk, "ann_date": cal[ann_idx], "sue": z})
            t += int(rng.normal(63, 4))
    prices = pd.DataFrame(100*np.exp(np.cumsum(ret, axis=0)), index=cal, columns=tickers)
    events = pd.DataFrame(ev_rows).sort_values("ann_date").reset_index(drop=True)
    return prices, events


# ---------------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------------
def abnormal_returns(prices):
    """Daily log returns, cross-sectionally demeaned (market-neutral abnormal returns)."""
    r = np.log(prices).diff()
    return r.sub(r.mean(axis=1), axis=0)


def _entry_index(cal, ann_date):
    """First trading-day index strictly after the announcement (T+1)."""
    return cal.searchsorted(pd.Timestamp(ann_date), side="right")


def drift_profile(events, AR, hold=60, standardize=True):
    """
    b(k) = slope of (abnormal return on day k after entry) on standardized SUE,
    pooled across events. Returns (b, B, k_axis, n_used).
        b[k] = sum_e z_e * AR_{e,k} / sum_e z_e^2     (per-unit-SUE daily drift)
        B[h] = cumsum(b)                              (per-unit-SUE cumulative drift)
    """
    cal = AR.index
    cols = {c: i for i, c in enumerate(AR.columns)}
    A = AR.values
    z = events["sue"].values.astype(float)
    if standardize:
        z = (z - np.nanmean(z)) / (np.nanstd(z) + 1e-12)

    num = np.zeros(hold); den = 0.0; n_used = 0
    for e, row in events.reset_index(drop=True).iterrows():
        j = cols.get(row["ticker"])
        if j is None:
            continue
        t0 = _entry_index(cal, row["ann_date"])
        if t0 + hold > len(cal):
            continue
        seg = A[t0:t0+hold, j]
        if np.isnan(seg).any():
            continue
        num += z[e] * seg
        den += z[e] ** 2
        n_used += 1
    b = num / (den + 1e-12)
    return b, np.cumsum(b), np.arange(hold), n_used


def fit_decay(b):
    """Fit b(k) ~ b0 * exp(-k/tau) on the LEADING high-signal window (before the noisy
    tail), which is where the decay timescale is identifiable. Returns (b0, tau, half_life)."""
    if len(b) < 4 or b[0] <= 0:
        return np.nan, np.nan, np.nan
    thr = 0.15 * b[0]                      # leading run while drift stays well above noise
    K = 0
    while K + 1 < len(b) and b[K + 1] > thr:
        K += 1
    K = max(K, 3)
    k = np.arange(K + 1)
    bb = b[:K + 1]
    m = bb > 0
    if m.sum() < 3:
        return np.nan, np.nan, np.nan
    coef = np.polyfit(k[m], np.log(bb[m]), 1)          # slope = -1/tau
    tau = -1.0 / coef[0] if coef[0] < 0 else np.inf
    b0 = np.exp(coef[1])
    half_life = tau * np.log(2) if np.isfinite(tau) else np.inf
    return b0, tau, half_life


def newey_west_t(x, L):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 5:
        return 0.0
    xm = x - x.mean(); g0 = (xm @ xm) / n; var = g0
    for k in range(1, min(L, n-1) + 1):
        gk = (xm[k:] @ xm[:-k]) / n
        var += 2 * (1 - k/(L+1)) * gk
    se = np.sqrt(max(var, 1e-18) / n)
    return float(x.mean() / se) if se > 0 else 0.0


def calendar_time_portfolio(events, AR, hold=60, standardize_daily=True):
    """
    Calendar-time long-short PEAD book: each day, every event still inside its
    [entry, entry+hold) window contributes its ticker's abnormal return weighted by
    its SUE; dollar-neutral. Aggregating to calendar time is what makes inference
    honest under overlapping windows + earnings-season clustering.
    Returns a daily return Series.
    """
    cal = AR.index; cols = {c: i for i, c in enumerate(AR.columns)}
    A = AR.values
    z_all = (events["sue"] - events["sue"].mean()) / (events["sue"].std() + 1e-12)
    # active weight matrix accumulation
    w = np.zeros((len(cal), AR.shape[1]))
    for e, row in events.reset_index(drop=True).iterrows():
        j = cols.get(row["ticker"])
        if j is None:
            continue
        t0 = _entry_index(cal, row["ann_date"])
        t1 = min(t0 + hold, len(cal))
        if t0 >= len(cal):
            continue
        w[t0:t1, j] += z_all.iloc[e]
    if standardize_daily:
        gross = np.abs(w).sum(axis=1, keepdims=True) + 1e-12
        w = w / gross
    port = np.nansum(w * np.nan_to_num(A), axis=1)
    return pd.Series(port, index=cal)


def durability_by_year(port):
    """Annualized IR per calendar year + linear trend (negative => fading)."""
    df = port.to_frame("r"); df["year"] = df.index.year
    rows = []
    for y, g in df.groupby("year"):
        r = g["r"].values
        ir = np.sqrt(252) * r.mean() / (r.std() + 1e-12)
        rows.append({"year": y, "IR": round(float(ir), 3), "t_NW": round(newey_west_t(r, 20), 2)})
    out = pd.DataFrame(rows)
    if len(out) >= 3:
        slope = np.polyfit(out["year"], out["IR"], 1)[0]
        out.attrs["trend_per_year"] = float(slope)
    return out


def sue_persistence(events):
    """Bernard-Thomas: corr(SUE_t, SUE_{t+1}) within ticker (forward-looking nugget)."""
    pairs = []
    for tk, g in events.sort_values("ann_date").groupby("ticker"):
        s = g["sue"].values
        if len(s) >= 2:
            pairs.append(np.column_stack([s[:-1], s[1:]]))
    if not pairs:
        return np.nan, 0.0, 0
    M = np.vstack(pairs)
    rho = np.corrcoef(M[:, 0], M[:, 1])[0, 1]
    n = len(M)
    t = rho * np.sqrt(max(n-2, 1) / max(1 - rho**2, 1e-12))
    return float(rho), float(t), n


# ---------------------------------------------------------------------------
# MAIN  (walk-forward flavor: estimate decay on train events, evaluate OOS)
# ---------------------------------------------------------------------------
def main():
    prices, events = make_synthetic_pead()
    AR = abnormal_returns(prices)
    hold = 60

    # walk-forward split on event time: estimate decay/h* on first 60% of events
    cut = events["ann_date"].quantile(0.60)
    train_ev = events[events["ann_date"] <= cut]
    test_ev = events[events["ann_date"] > cut]

    b, B, kax, n = drift_profile(train_ev, AR, hold=hold)
    b0, tau, half_life = fit_decay(b)
    h_star = int(np.argmax(B) + 1)                 # horizon where cumulative drift peaks

    # OOS tradable portfolio at the chosen horizon
    port_oos = calendar_time_portfolio(test_ev, AR, hold=h_star)
    ir_oos = np.sqrt(252) * port_oos.mean() / (port_oos.std() + 1e-12)
    t_oos = newey_west_t(port_oos.values, L=h_star)

    dur = durability_by_year(calendar_time_portfolio(events, AR, hold=h_star))
    rho, t_rho, n_pairs = sue_persistence(events)

    print("# PEAD event-study (SYNTHETIC validation; true half-life =",
          round(15*np.log(2), 1), "days, yearly fade injected)\n")
    print(f"events: {len(events)} (train {len(train_ev)} / test {len(test_ev)}), "
          f"profile used {n} events")
    print(f"(1)/(2) decay:   fitted tau={tau:.1f}  ->  HALF-LIFE = {half_life:.1f} trading days")
    print(f"        optimal holding horizon h* = {h_star} days "
          f"(cumulative drift per unit SUE = {B[h_star-1]*100:.2f}% )")
    print(f"        marginal drift day1={b[0]*1e4:.1f}bp  day5={b[4]*1e4:.1f}bp  "
          f"day20={b[19]*1e4:.1f}bp  day40={b[39]*1e4:.1f}bp")
    print(f"(3) durability:  OOS IR={ir_oos:.2f} (NW t={t_oos:.1f}); "
          f"trend/yr={dur.attrs.get('trend_per_year', float('nan')):+.3f} "
          f"(negative => PEAD fading across time)")
    print(f"(4) SUE persistence: corr(SUE_t, SUE_t+1) = {rho:.3f} (t={t_rho:.1f}, n={n_pairs})")
    print("\nIR by year:")
    print(dur.to_string(index=False))

    # figures
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
        ax[0].bar(kax, b*1e4, color="steelblue", alpha=.7, label="b(k) measured")
        if np.isfinite(tau):
            ax[0].plot(kax, b0*np.exp(-kax/tau)*1e4, "r-", lw=2, label=f"fit, t½={half_life:.0f}d")
        ax[0].axhline(0, color="k", lw=.6); ax[0].set_title("Marginal drift per unit SUE (bp/day)")
        ax[0].set_xlabel("days after entry"); ax[0].legend()
        ax[1].plot(kax+1, B*100, lw=1.6); ax[1].axvline(h_star, color="r", ls="--", label=f"h*={h_star}")
        ax[1].set_title("Cumulative drift B(h) per unit SUE (%)"); ax[1].set_xlabel("holding days"); ax[1].legend()
        ax[2].bar(dur["year"], dur["IR"], color="seagreen", alpha=.75)
        ax[2].set_title("Durability: tradable IR by year"); ax[2].axhline(0, color="k", lw=.6)
        plt.tight_layout(); plt.savefig("pead_results.png", dpi=110)
        print("\n# wrote pead_results.png")
    except Exception as e:
        print("plot skipped:", e)


if __name__ == "__main__":
    main()
