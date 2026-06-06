#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sue_pead.py — build the classic PEAD signal from EDGAR earnings, NO analyst data needed.

The original post-earnings-announcement-drift signal (Foster 1977; Bernard & Thomas 1989)
uses a TIME-SERIES expectation of earnings, not analyst consensus:

    SUE_{i,t} = (E_{i,t} - E_{i,t-4}) / sigma_i      (seasonal random walk)

where E is quarterly EPS, E_{i,t-4} is the same quarter a year earlier, and sigma_i is the
std dev of those year-over-year changes over a trailing window (default 8 quarters).
High SUE -> positive surprise -> price tends to drift up for weeks (underreaction).

This is fully reproducible from free SEC EDGAR data and is point-in-time by construction
(each SUE is dated by the FILING date, entered with a T+1 lag).

Pipeline:
    quarterly_eps()  ->  compute_sue()  ->  sue_to_daily_signal()
The daily signal is a (date x ticker) frame you can drop straight into a cross-sectional
backtest (e.g. the belief_state_p0_runner load_panel/feature seam).
"""

import numpy as np
import pandas as pd
from edgar_client import EdgarClient
from fundamentals_loader import quarterly_eps


def compute_sue(eps_panel, window=8, min_obs=6, clip=8.0):
    """
    Add a seasonal-random-walk SUE to a quarterly EPS panel.

    eps_panel: columns [ticker, fy, fp, end, eps, filed] (from fundamentals_loader.quarterly_eps).
    window: trailing quarters used to estimate the std of YoY EPS changes.
    clip: winsorize |SUE| at this cap (std units). Essential: when the trailing sigma is
          ~0 (near-constant EPS, or FY4-derived quarters), raw SUE explodes to +/-hundreds and
          a single outlier destroys the cross-sectional z-score. The PEAD literature always
          winsorizes SUE; clip also maps +/-inf from sigma->0 to the cap.
    Returns the panel with new columns: yoy_change, sue.
    """
    df = eps_panel.sort_values(["ticker", "end"]).copy()
    df["yoy_change"] = df.groupby("ticker")["eps"].diff(4)   # E_t - E_{t-4}
    # trailing std of YoY changes (shifted by 1 so sigma uses only prior quarters)
    df["_sigma"] = (df.groupby("ticker")["yoy_change"]
                      .transform(lambda s: s.shift(1).rolling(window, min_periods=min_obs).std()))
    sue = df["yoy_change"] / df["_sigma"]
    df["sue"] = sue.replace([np.inf, -np.inf], np.nan).clip(-clip, clip)   # winsorize
    return df.drop(columns="_sigma")


def sue_to_daily_signal(sue_panel, calendar, exec_lag=1, hold_days=60,
                        standardize=True):
    """
    Map sparse, event-dated SUE values onto a daily (date x ticker) signal frame.

    Each SUE becomes active 'exec_lag' trading days after its FILING date (T+1 by default,
    so you never trade on the same print) and stays active for 'hold_days' (the drift window),
    then decays to 0. If a newer earnings filing arrives, it overrides.

    calendar: DatetimeIndex of trading days.
    standardize: cross-sectionally z-score each day (the usual ranking input).
    Returns a (len(calendar) x n_tickers) DataFrame.
    """
    cal = pd.DatetimeIndex(calendar).sort_values()
    tickers = sorted(sue_panel["ticker"].unique())
    sig = pd.DataFrame(0.0, index=cal, columns=tickers)

    for tk, g in sue_panel.dropna(subset=["sue", "filed"]).groupby("ticker"):
        g = g.sort_values("filed")
        for _, row in g.iterrows():
            # first trading day strictly after filing + (exec_lag-1)
            pos = cal.searchsorted(pd.Timestamp(row["filed"]), side="right")
            start = pos + (exec_lag - 1)
            if start >= len(cal):
                continue
            end = min(start + hold_days, len(cal))
            sig.iloc[start:end, sig.columns.get_loc(tk)] = row["sue"]

    if standardize:
        mu = sig.mean(axis=1)
        sd = sig.std(axis=1).replace(0, np.nan)
        sig = sig.sub(mu, axis=0).div(sd, axis=0).fillna(0.0)
    return sig


def build_pead_signal(user_agent, tickers, calendar,
                      window=8, exec_lag=1, hold_days=60):
    """End-to-end convenience: tickers + trading calendar -> daily PEAD signal frame."""
    ec = EdgarClient(user_agent)
    eps = quarterly_eps(ec, tickers)
    if eps.empty:
        raise RuntimeError("No EPS pulled — check tickers/User-Agent/network.")
    sue = compute_sue(eps, window=window)
    return sue_to_daily_signal(sue, calendar, exec_lag=exec_lag, hold_days=hold_days)


if __name__ == "__main__":
    import sys
    ua = sys.argv[1] if len(sys.argv) > 1 else "Example User example@example.com"
    ec = EdgarClient(ua)
    eps = quarterly_eps(ec, ["AAPL", "MSFT", "NVDA"])
    sue = compute_sue(eps)
    print(sue[["ticker", "fp", "end", "eps", "yoy_change", "sue"]].tail(12).to_string(index=False))
    cal = pd.bdate_range("2018-01-01", "2024-12-31")
    daily = sue_to_daily_signal(sue, cal)
    print("\nDaily signal shape:", daily.shape, "| nonzero days:", (daily != 0).any(axis=1).sum())
