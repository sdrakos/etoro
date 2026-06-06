#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
leadlag_event_study.py — cross-firm (same-industry) earnings lead-lag.

Question: when firm i surprises in earnings, does a SAME-INDUSTRY peer j drift in the
following weeks? (Cohen-Frazzini economic links; Menzly-Ozbas industry information diffusion.)
The mechanism is slow information diffusion across linked firms.

Construction (reuses the PEAD event-study machinery):
  - For each announcement (firm i, date, SUE_i), emit "peer events" (peer j, date, SUE_i)
    for every same-industry peer j != i. Then measure j's abnormal drift vs SUE_i.
  - Default uses MARKET-neutral abnormal returns (NOT sector-neutral): same-industry
    lead-lag partly lives at the sector level, so sector-demeaning would erase it.
  - Key confound: peers announce in clusters (earnings season), so j often announces near i.
    The own-firm PEAD of j could masquerade as a peer effect. The `exclude_own` control
    drops peer-events whose window overlaps j's OWN announcement window, isolating the
    genuine cross-firm signal.

Relationship map = same SIC code (free, from EDGAR submissions: 'sicCode').

Runs on your machine (EDGAR/prices blocked in sandbox). Default here is a synthetic
self-test with a KNOWN injected lead-lag (separate from own PEAD) to validate recovery.
"""

import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pead_event_study as pes

RNG = np.random.default_rng(7)


# ---------------------------------------------------------------------------
# Relationship map
# ---------------------------------------------------------------------------
def build_sic_map(user_agent, tickers):
    """Pull each ticker's SIC code from EDGAR submissions (runs on your machine)."""
    for p in [os.path.expanduser("~/.claude/skills/sec-edgar/scripts"),
              os.path.expanduser("~/skills/sec-edgar/scripts"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "sec-edgar", "scripts"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skill", "sec-edgar", "scripts")]:
        if os.path.isdir(p):
            sys.path.insert(0, p); break
    from edgar_client import EdgarClient
    ec = EdgarClient(user_agent)
    sic = {}
    for t in tickers:
        try:
            sub = ec.submissions(t)
            if sub and sub.get("sic"):                 # EDGAR submissions field is 'sic', not 'sicCode'
                sic[t.upper()] = str(sub["sic"])
        except Exception:
            continue
    return sic


def peers_from_groups(group_map):
    """group_map: {ticker: group_id (SIC/sector)} -> {ticker: [same-group peers]}."""
    by_group = {}
    for tk, g in group_map.items():
        by_group.setdefault(g, []).append(tk)
    peers = {}
    for tk, g in group_map.items():
        peers[tk] = [o for o in by_group[g] if o != tk]
    return peers


# ---------------------------------------------------------------------------
# Build peer events from own-firm announcements
# ---------------------------------------------------------------------------
def build_peer_events(events, peers, hold=60, max_peers=12, exclude_own=True, own_pad=None):
    """
    Turn own-firm announcements into peer events.
    events : [ticker, ann_date, sue]  (own-firm announcements with SUE)
    Returns: [ticker(=peer j), ann_date, sue(=announcer's standardized SUE)]
    exclude_own: drop a peer event for j if j has its OWN announcement within
                 +/- own_pad days (default = hold) of that date (kills own-PEAD leakage).
    """
    own_pad = hold if own_pad is None else own_pad
    ev = events.dropna(subset=["sue"]).copy()
    ev["ann_date"] = pd.to_datetime(ev["ann_date"])
    z = (ev["sue"] - ev["sue"].mean()) / (ev["sue"].std() + 1e-12)
    ev = ev.assign(z=z.values)

    own_dates = {tk: np.sort(g["ann_date"].values.astype("datetime64[D]").astype(int))
                 for tk, g in ev.groupby("ticker")}
    pad = np.timedelta64(own_pad, "D").astype("timedelta64[D]").astype(int)

    rows = []
    for _, r in ev.iterrows():
        i = r["ticker"]; a = np.datetime64(r["ann_date"], "D").astype(int); zi = r["z"]
        plist = peers.get(i, [])
        if max_peers and len(plist) > max_peers:
            plist = list(RNG.choice(plist, size=max_peers, replace=False))
        for j in plist:
            if exclude_own and j in own_dates:
                d = own_dates[j]
                k = np.searchsorted(d, a)
                near = (k < len(d) and abs(d[k]-a) <= pad) or (k > 0 and abs(d[k-1]-a) <= pad)
                if near:
                    continue
            rows.append((j, r["ann_date"], zi))
    return pd.DataFrame(rows, columns=["ticker", "ann_date", "sue"])


# ---------------------------------------------------------------------------
# Synthetic with a KNOWN lead-lag (separate from own PEAD)
# ---------------------------------------------------------------------------
def make_synthetic_leadlag(n_tickers=120, n_groups=6, start="2012-01-01", end="2024-12-31",
                           tau_own=12.0, tau_lead=18.0, a_own=0.0010,
                           a_lead0=0.0009, a_lead_end=0.0002, sue_rho=0.30,
                           hold=60, seed=7):
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range(start, end); T = len(cal)
    yrf = (cal.year.values - cal.year.min()) / (cal.year.max() - cal.year.min())
    a_lead_t = a_lead0 + (a_lead_end - a_lead0) * yrf

    tickers = [f"T{i:03d}" for i in range(n_tickers)]
    group = {tk: f"G{i % n_groups}" for i, tk in enumerate(tickers)}
    peers = peers_from_groups(group)
    col = {tk: i for i, tk in enumerate(tickers)}

    ret = rng.normal(0, 0.015, (T, n_tickers)) + rng.normal(0, 0.008, (T, 1))

    # own announcements + own PEAD
    ev = []
    for tk in tickers:
        t = rng.integers(20, 60); prev = rng.normal()
        while t < T - hold - 2:
            z = sue_rho*prev + np.sqrt(1-sue_rho**2)*rng.normal(); prev = z
            entry = t+1; ks = np.arange(hold)
            ret[entry:entry+hold, col[tk]] += a_own * z * np.exp(-ks/tau_own)
            ev.append({"ticker": tk, "ann_date": cal[t], "sue": z})
            t += int(rng.normal(63, 4))
    events = pd.DataFrame(ev)

    # cross-firm lead-lag: peer j reacts (T+1) to i's surprise, decaying with tau_lead
    zall = (events["sue"] - events["sue"].mean()) / (events["sue"].std() + 1e-12)
    ks = np.arange(hold)
    for (_, r), zi in zip(events.iterrows(), zall):
        a = cal.searchsorted(pd.Timestamp(r["ann_date"]), side="right")  # T+1
        if a >= T:
            continue
        h = min(hold, T-a)
        bump = a_lead_t[a] * zi * np.exp(-ks[:h]/tau_lead)
        for j in peers[r["ticker"]]:
            ret[a:a+h, col[j]] += bump
    prices = pd.DataFrame(100*np.exp(np.cumsum(ret, axis=0)), index=cal, columns=tickers)
    return prices, events, group


# ---------------------------------------------------------------------------
# Daily signal panels + Fama-MacBeth (the correct own/peer separation)
# ---------------------------------------------------------------------------
def build_daily_signal(events, cal, tickers, hold, to_peers=None):
    """(date x ticker) panel: each announcement's standardized SUE is active over
    [T+1, T+1+hold). If to_peers is given, the surprise is routed to the announcer's
    PEERS (summed) instead of itself -> the peer-implied surprise."""
    col = {t: i for i, t in enumerate(tickers)}
    z = (events["sue"] - events["sue"].mean()) / (events["sue"].std() + 1e-12)
    S = np.zeros((len(cal), len(tickers)))
    for (_, r), zi in zip(events.iterrows(), z):
        t0 = cal.searchsorted(pd.Timestamp(r["ann_date"]), side="right")   # T+1
        if t0 >= len(cal):
            continue
        t1 = min(t0 + hold, len(cal))
        targets = [r["ticker"]] if to_peers is None else to_peers.get(r["ticker"], [])
        for tk in targets:
            j = col.get(tk)
            if j is not None:
                S[t0:t1, j] += zi
    return S


def fama_macbeth(AR, peer, own=None):
    """Daily cross-sectional regression of abnormal returns on the peer signal
    (and own signal if given). Returns daily coefficient Series (peer, own).
    The peer coefficient series IS the lead-lag factor return, controlling for own PEAD."""
    A = AR.values
    cal = AR.index
    bp, bo, days = [], [], []
    for t in range(len(cal)):
        y = A[t]
        cols = [peer[t]]
        if own is not None:
            cols.append(own[t])
        X = np.column_stack([np.ones_like(y)] + cols)
        m = np.isfinite(y) & np.isfinite(X).all(axis=1)
        if m.sum() < 10 or np.nanstd(peer[t][m]) < 1e-9:
            continue
        beta, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
        bp.append(beta[1]); bo.append(beta[2] if own is not None else np.nan)
        days.append(cal[t])
    return pd.Series(bp, index=days), pd.Series(bo, index=days)


def _factor_stats(series, L=60):
    r = series.values
    ir = float(np.sqrt(252) * r.mean() / (r.std() + 1e-12))
    return round(ir, 3), round(pes.newey_west_t(r, L), 2)


def _durability(series):
    df = series.to_frame("r"); df["year"] = df.index.year
    rows = []
    for y, g in df.groupby("year"):
        v = g["r"].values
        rows.append({"year": int(y), "IR": round(float(np.sqrt(252)*v.mean()/(v.std()+1e-12)), 3),
                     "t_NW": round(pes.newey_west_t(v, 20), 2)})
    out = pd.DataFrame(rows)
    trend = float(np.polyfit(out["year"], out["IR"], 1)[0]) if len(out) >= 3 else float("nan")
    return out, trend


def run(prices, events, group_map, hold=60, market_neutral=True, outprefix="leadlag"):
    peers = peers_from_groups(group_map)
    cal = prices.index; tickers = list(prices.columns)
    AR = pes.abnormal_returns(prices) if market_neutral else \
        __import__("run_pead_real").abnormal_returns(prices, group_map)

    own_sig = build_daily_signal(events, cal, tickers, hold)                  # to self
    peer_sig = build_daily_signal(events, cal, tickers, hold, to_peers=peers)  # to peers

    peer_joint, own_beta = fama_macbeth(AR, peer_sig, own=own_sig)   # peer controlling for own
    peer_uni, _ = fama_macbeth(AR, peer_sig, own=None)              # peer alone (contaminated)

    ir_j, t_j = _factor_stats(peer_joint, L=hold)
    ir_u, t_u = _factor_stats(peer_uni, L=hold)
    ir_o, t_o = _factor_stats(own_beta.dropna(), L=hold)
    dur, trend = _durability(peer_joint)

    res = {
        "market_neutral": market_neutral, "hold": hold,
        "peer_CLEAN_controls_own": {"IR": ir_j, "t_NW": t_j,
                                    "trend_per_year": round(trend, 4),
                                    "IR_by_year": dur.to_dict("records")},
        "peer_contaminated_no_control": {"IR": ir_u, "t_NW": t_u},
        "own_PEAD_for_reference": {"IR": ir_o, "t_NW": t_o},
        "note": ("peer_CLEAN is the genuine lead-lag (own PEAD regressed out each day, "
                 "Fama-MacBeth). If contaminated >> clean, the naive peer effect was mostly "
                 "own-firm PEAD leaking through earnings-season clustering."),
    }
    with open(f"{outprefix}_results.json", "w") as f:
        json.dump(res, f, indent=2)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
        ax[0].plot(peer_joint.index, peer_joint.cumsum(), color="darkorange", lw=1.3, label="peer (controls own)")
        ax[0].plot(peer_uni.index, peer_uni.cumsum(), color="gray", lw=1.0, ls="--", label="peer (no control)")
        ax[0].set_title("Cumulative lead-lag factor return"); ax[0].legend(); ax[0].axhline(0, color="k", lw=.5)
        ax[1].plot(own_beta.dropna().index, own_beta.dropna().cumsum(), color="steelblue", lw=1.2)
        ax[1].set_title("Own-PEAD factor (reference)"); ax[1].axhline(0, color="k", lw=.5)
        ax[2].bar(dur["year"], dur["IR"], color="chocolate", alpha=.75); ax[2].axhline(0, color="k", lw=.6)
        ax[2].set_title("Durability: clean lead-lag IR by year")
        plt.tight_layout(); plt.savefig(f"{outprefix}_results.png", dpi=110)
    except Exception as e:
        print("plot skipped:", e)
    return res


def _print(res):
    c = res["peer_CLEAN_controls_own"]; u = res["peer_contaminated_no_control"]
    o = res["own_PEAD_for_reference"]
    print(f"market_neutral={res['market_neutral']}, hold={res['hold']}")
    print(f"CLEAN lead-lag (controls own PEAD): IR {c['IR']} (NW t={c['t_NW']}), "
          f"trend/yr {c['trend_per_year']}")
    print(f"contaminated peer (no control):     IR {u['IR']} (NW t={u['t_NW']})")
    print(f"own-PEAD reference:                  IR {o['IR']} (NW t={o['t_NW']})")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hold", type=int, default=60)
    a = ap.parse_args()
    if a.selftest:
        prices, events, group = make_synthetic_leadlag()
        print("# SELF-TEST (synthetic; injected lead-lag half-life =",
              round(18*np.log(2), 1), "d, separate from own PEAD)")
        _print(run(prices, events, group, hold=a.hold, outprefix="leadlag_selftest"))
        return
    ap.error("real runs: build group_map via build_sic_map(user_agent, tickers) and call "
             "run(prices, events, group_map); use --selftest here.")


if __name__ == "__main__":
    main()
