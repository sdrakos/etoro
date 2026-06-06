#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pead_real.py — orchestrate the OWN-FIRM PEAD on real data.

It wires three pieces you already have:
  1. sec-edgar skill   -> quarterly EPS from EDGAR -> seasonal-random-walk SUE  (events)
  2. your price panel  -> daily adjusted closes (date x ticker)                 (prices)
  3. pead_event_study  -> drift profile, half-life, calendar-time NW test,      (analysis)
                          durability by year, SUE persistence

Runs on YOUR machine (data.sec.gov + price vendors are blocked in the sandbox).
Swap the two loaders for your real sources; everything downstream is unchanged.

    python run_pead_real.py --selftest                 # synthetic wiring check (no network)
    python run_pead_real.py --prices prices.csv \
        --tickers AAPL,MSFT,NVDA,... \
        --user-agent "Stefanos Drakos stefanos@agelai.gr" \
        --sectors sectors.csv --hold 60

prices.csv : first column = date, remaining columns = tickers (adjusted close).
sectors.csv: two columns  ticker,sector   (optional; enables sector-neutral returns).
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd

# import the analysis module (same folder)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pead_event_study as pes


# locate the installed sec-edgar skill scripts (edit if yours lives elsewhere)
SKILL_CANDIDATES = [
    os.path.expanduser("~/.claude/skills/sec-edgar/scripts"),
    os.path.expanduser("~/skills/sec-edgar/scripts"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "sec-edgar", "scripts"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skill", "sec-edgar", "scripts"),
]


# ---------------------------------------------------------------------------
# Loaders (swap these for your real sources)
# ---------------------------------------------------------------------------
def load_prices_csv(path):
    """Wide daily price panel: index=date, columns=tickers (adjusted close)."""
    df = pd.read_csv(path)
    df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
    return df.set_index(df.columns[0]).sort_index()


def load_sectors_csv(path):
    if not path:
        return None
    s = pd.read_csv(path)
    return dict(zip(s.iloc[:, 0].astype(str), s.iloc[:, 1].astype(str)))


def load_events_from_edgar(tickers, user_agent):
    """Use the sec-edgar skill to build [ticker, ann_date, sue] (point-in-time)."""
    for p in SKILL_CANDIDATES:
        if os.path.isdir(p):
            sys.path.insert(0, p)
            break
    else:
        raise FileNotFoundError(
            "sec-edgar skill scripts not found. Set the path in SKILL_CANDIDATES.")
    from edgar_client import EdgarClient          # noqa: E402
    from fundamentals_loader import quarterly_eps  # noqa: E402
    from sue_pead import compute_sue               # noqa: E402

    ec = EdgarClient(user_agent)
    eps = quarterly_eps(ec, tickers)
    if eps.empty:
        raise RuntimeError("No EPS pulled from EDGAR — check tickers / User-Agent / network.")
    sue = compute_sue(eps)
    ev = (sue.dropna(subset=["sue"])
             .rename(columns={"filed": "ann_date"})[["ticker", "ann_date", "sue"]]
             .reset_index(drop=True))
    return ev


# ---------------------------------------------------------------------------
# Abnormal returns: market-neutral (default) or SECTOR-neutral (preferred for PEAD)
# ---------------------------------------------------------------------------
def abnormal_returns(prices, sector_map=None):
    """Daily log returns demeaned cross-sectionally. If sector_map is given, demean
    WITHIN each sector each day (sector-neutral) — the standard, cleaner PEAD setup,
    since it strips out sector-wide moves, not just the whole-market move."""
    r = np.log(prices).diff()
    if not sector_map:
        return r.sub(r.mean(axis=1), axis=0)
    sectors = pd.Series({c: sector_map.get(str(c), "_NA") for c in prices.columns})
    out = r.copy()
    for sec, cols in sectors.groupby(sectors).groups.items():
        cols = list(cols)
        out[cols] = r[cols].sub(r[cols].mean(axis=1), axis=0)
    return out


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(prices, events, sector_map=None, hold=60, train_frac=0.60, outprefix="pead_real"):
    AR = abnormal_returns(prices, sector_map)

    cut = events["ann_date"].quantile(train_frac)
    train_ev = events[events["ann_date"] <= cut]
    test_ev = events[events["ann_date"] > cut]

    b, B, kax, n = pes.drift_profile(train_ev, AR, hold=hold)
    b0, tau, half_life = pes.fit_decay(b)
    h_star = int(np.argmax(B) + 1)

    port_oos = pes.calendar_time_portfolio(test_ev, AR, hold=h_star)
    ir_oos = float(np.sqrt(252) * port_oos.mean() / (port_oos.std() + 1e-12))
    t_oos = pes.newey_west_t(port_oos.values, L=h_star)

    dur = pes.durability_by_year(pes.calendar_time_portfolio(events, AR, hold=h_star))
    rho, t_rho, n_pairs = pes.sue_persistence(events)

    res = {
        "n_events": int(len(events)), "n_train": int(len(train_ev)),
        "n_test": int(len(test_ev)), "profile_events_used": int(n),
        "sector_neutral": bool(sector_map),
        "half_life_days": None if not np.isfinite(half_life) else round(half_life, 2),
        "optimal_horizon_days": h_star,
        "cum_drift_per_SUE_pct": round(float(B[h_star-1]) * 100, 3),
        "marginal_drift_bp": {f"day{d+1}": round(float(b[d])*1e4, 2)
                              for d in [0, 4, 9, 19, 39] if d < len(b)},
        "oos_IR": round(ir_oos, 3), "oos_t_NW": round(t_oos, 2),
        "durability_trend_per_year": round(float(dur.attrs.get("trend_per_year", float("nan"))), 4),
        "IR_by_year": dur.to_dict(orient="records"),
        "sue_persistence_rho": round(rho, 3), "sue_persistence_t": round(t_rho, 2),
    }
    with open(f"{outprefix}_results.json", "w") as f:
        json.dump(res, f, indent=2)

    # figure (reuse the analysis module's style)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
        ax[0].bar(kax, b*1e4, color="steelblue", alpha=.7, label="b(k)")
        if np.isfinite(tau):
            ax[0].plot(kax, b0*np.exp(-kax/tau)*1e4, "r-", lw=2,
                       label=f"fit t½={half_life:.0f}d")
        ax[0].axhline(0, color="k", lw=.6); ax[0].legend()
        ax[0].set_title("Marginal drift / unit SUE (bp/day)"); ax[0].set_xlabel("days after entry")
        ax[1].plot(kax+1, B*100, lw=1.6); ax[1].axvline(h_star, color="r", ls="--", label=f"h*={h_star}")
        ax[1].set_title("Cumulative drift B(h) / unit SUE (%)"); ax[1].set_xlabel("holding days"); ax[1].legend()
        ax[2].bar(dur["year"], dur["IR"], color="seagreen", alpha=.75); ax[2].axhline(0, color="k", lw=.6)
        ax[2].set_title("Durability: IR by year")
        plt.tight_layout(); plt.savefig(f"{outprefix}_results.png", dpi=110)
    except Exception as e:
        print("plot skipped:", e)

    return res


def _print(res):
    print(f"events {res['n_events']} (train {res['n_train']}/test {res['n_test']}), "
          f"sector_neutral={res['sector_neutral']}")
    print(f"half-life = {res['half_life_days']} d | h* = {res['optimal_horizon_days']} d "
          f"| cum drift/SUE = {res['cum_drift_per_SUE_pct']}%")
    print(f"marginal drift (bp): {res['marginal_drift_bp']}")
    print(f"OOS IR = {res['oos_IR']} (NW t={res['oos_t_NW']}) | "
          f"durability trend/yr = {res['durability_trend_per_year']}")
    print(f"SUE persistence rho = {res['sue_persistence_rho']} (t={res['sue_persistence_t']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="synthetic wiring check, no network")
    ap.add_argument("--prices"); ap.add_argument("--tickers")
    ap.add_argument("--user-agent"); ap.add_argument("--sectors")
    ap.add_argument("--hold", type=int, default=60)
    a = ap.parse_args()

    if a.selftest:
        prices, events = pes.make_synthetic_pead()
        # fake a sector map (5 sectors) to exercise the sector-neutral path
        secs = {c: f"SEC{i%5}" for i, c in enumerate(prices.columns)}
        print("# SELF-TEST (synthetic; proves wiring + sector-neutral path)")
        _print(run(prices, events, sector_map=secs, hold=a.hold, outprefix="pead_real_selftest"))
        return

    if not (a.prices and a.tickers and a.user_agent):
        ap.error("real run needs --prices, --tickers and --user-agent (or use --selftest)")
    prices = load_prices_csv(a.prices)
    sector_map = load_sectors_csv(a.sectors)
    tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]
    events = load_events_from_edgar(tickers, a.user_agent)
    # keep only tickers we actually have prices for
    events = events[events["ticker"].isin(prices.columns)].reset_index(drop=True)
    _print(run(prices, events, sector_map=sector_map, hold=a.hold))


if __name__ == "__main__":
    main()
