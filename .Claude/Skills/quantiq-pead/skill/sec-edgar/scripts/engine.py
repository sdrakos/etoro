#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py — the full QuantIQ pipeline in one runner.

    signals  ->  utility gate  ->  risk-parity combine  ->  regime (vol) layer  ->  book

Pieces (all in this skill):
  - signals      : own-PEAD + peer (same-industry) lead-lag, as (date x ticker) frames
  - gate.py      : keep only signals with durable, utility-weighted, significant edge
  - combine_signals.py : merge survivors by risk parity / ERC (equal risk, not equal capital)
  - regime.py    : volatility-target the book (size down in stormy regimes) — the risk brake

Design stance (proven by your own DER results + Jane Street's public material):
no model "learns direction"; weak theory-driven signals are filtered, combined with discipline,
and wrapped in regime-aware risk. Capacity is risk, not virtue.

Runs on your machine with real data; here `--selftest` validates the whole chain on synthetic
data with a KNOWN signal + a KNOWN volatility regime (so the brake has something to do).
"""

import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combine_signals as cs
import gate as gt
import regime as rg


# ---------------------------------------------------------------------------
# Production signal builders (own PEAD + peer lead-lag) from events + groups
# ---------------------------------------------------------------------------
def _daily_from_events(events, cal, tickers, hold, peers=None):
    """(date x ticker) panel: each announcement's standardized SUE active over [T+1, T+1+hold).
    If peers given, route the surprise to the announcer's peers (summed)."""
    col = {t: i for i, t in enumerate(tickers)}
    z = (events["sue"] - events["sue"].mean()) / (events["sue"].std() + 1e-12)
    S = np.zeros((len(cal), len(tickers)))
    for (_, r), zi in zip(events.iterrows(), z):
        t0 = cal.searchsorted(pd.Timestamp(r["ann_date"]), side="right")
        if t0 >= len(cal):
            continue
        t1 = min(t0 + hold, len(cal))
        targets = peers.get(r["ticker"], []) if peers else [r["ticker"]]
        for tk in targets:
            j = col.get(tk)
            if j is not None:
                S[t0:t1, j] += zi
    return pd.DataFrame(S, index=cal, columns=tickers)


def build_signals(events, group_map, cal, tickers, hold=60):
    """Return {'own_pead':..., 'peer_leadlag':...} as (date x ticker) frames."""
    by_g = {}
    for tk, g in group_map.items():
        by_g.setdefault(g, []).append(tk)
    peers = {tk: [o for o in by_g[group_map[tk]] if o != tk] for tk in group_map}
    return {"own_pead": _daily_from_events(events, cal, tickers, hold),
            "peer_leadlag": _daily_from_events(events, cal, tickers, hold, peers=peers)}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
def _max_dd(cum):
    return float((cum - cum.cummax()).min())


def run(signals, ret, target_vol=0.10, t_thresh=2.0, regime_lookback=20,
        market_state=None, outprefix="engine"):
    # 1) gate: which signals carry durable, utility-weighted edge
    tbl, passed = gt.gate(signals, ret, t_thresh=t_thresh)
    use = passed if passed else list(signals)        # fallback: keep all (flagged below)

    # 2) combine survivors by risk parity (real risk from each signal's P&L)
    combined, w = cs.combine({k: signals[k] for k in use}, returns=ret, method="inverse_vol")

    # 3) raw combined book P&L
    port = gt.signal_pnl(combined, ret).dropna()

    # 4) regime layer: volatility-target on the market state (or the book's own vol) — no look-ahead
    state = (market_state.reindex(port.index) if market_state is not None else port)
    scaled, mult = rg.apply_regime(port, state, mode="vol_target",
                                   target_vol=target_vol, lookback=regime_lookback)
    scaled = scaled.dropna()

    def stats(p):
        return dict(IR=round(float(np.sqrt(252)*p.mean()/(p.std()+1e-12)), 3),
                    t_NW=round(gt._nw_t(p.values, regime_lookback), 2),
                    ann_vol=round(float(p.std()*np.sqrt(252)), 3),
                    maxDD=round(_max_dd(p.cumsum()), 4))
    res = {
        "signals_passed_gate": use, "gate_fallback_used": (not passed),
        "weights": {k: round(float(v), 3) for k, v in w.items()},
        "raw": stats(port), "regime_scaled": stats(scaled),
        "gate_table": json.loads(tbl.to_json(orient="index")),
    }
    with open(f"{outprefix}_results.json", "w") as f:
        json.dump(res, f, indent=2)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
        ax[0].plot(port.index, port.cumsum(), label="raw combined", lw=1.2)
        ax[0].plot(scaled.index, scaled.cumsum(), label="regime-scaled", lw=1.4)
        ax[0].legend(); ax[0].set_title("Cumulative P&L (return units)"); ax[0].axhline(0, color="k", lw=.5)
        ax[1].plot(mult.reindex(port.index).index, mult.reindex(port.index).values, color="firebrick", lw=1)
        ax[1].set_title("Regime exposure multiplier"); ax[1].axhline(1, color="k", lw=.4)
        names = list(w.index); ax[2].bar(names, [w[n] for n in names], color="teal", alpha=.75)
        ax[2].set_title("Risk-parity weights")
        plt.tight_layout(); plt.savefig(f"{outprefix}_results.png", dpi=110)
    except Exception as e:
        print("plot skipped:", e)
    return res


# ---------------------------------------------------------------------------
# Synthetic self-test: known signal + known vol regime
# ---------------------------------------------------------------------------
def _selftest():
    rng = np.random.default_rng(11)
    cal = pd.bdate_range("2014-01-01", "2024-12-31"); T = len(cal)
    n = 120; tickers = [f"T{i:03d}" for i in range(n)]
    group = {tk: f"G{i % 6}" for i, tk in enumerate(tickers)}

    # quarterly events with AR(1) SUE
    ev = []
    for tk in tickers:
        t = rng.integers(20, 60); prev = rng.normal()
        while t < T - 65:
            z = 0.3*prev + np.sqrt(1-0.09)*rng.normal(); prev = z
            ev.append({"ticker": tk, "ann_date": cal[t], "sue": z}); t += int(rng.normal(63, 4))
    events = pd.DataFrame(ev)
    sig = build_signals(events, group, cal, tickers, hold=60)

    # market factor with vol clustering + a crisis crash window
    vol = 0.008 * (1 + 1.5*(np.sin(np.arange(T)/130)**2))
    crisis = slice(int(T*0.46), int(T*0.52))
    vol[crisis] *= 3.0
    mkt = rng.normal(0, vol)
    mkt[crisis] += -0.008                                   # sustained drawdown shock
    market_state = pd.Series(mkt, index=cal)

    # WEAK realistic drifts + idio + a mild signal-coupled beta leak (book carries net beta)
    own_z = sig["own_pead"].values; peer_z = sig["peer_leadlag"].values
    beta = 0.30 + 0.15*own_z                                # high-signal names = slightly higher beta
    idio = rng.normal(0, 0.014, (T, n))
    drift = 0.00030*own_z + 0.00020*peer_z
    ret = pd.DataFrame(drift + idio + beta*mkt[:, None], index=cal, columns=tickers)

    print("# SELF-TEST: full engine (weak signal + vol regime with a crisis)")
    res = run(sig, ret, target_vol=0.06, market_state=market_state, outprefix="engine_selftest")
    print("passed gate:", res["signals_passed_gate"], "| weights:", res["weights"])
    print("raw          :", res["raw"])
    print("regime-scaled :", res["regime_scaled"])
    dd_raw, dd_sc = res["raw"]["maxDD"], res["regime_scaled"]["maxDD"]
    print(f"=> maxDD {dd_raw:+.4f} -> {dd_sc:+.4f} "
          f"({'brake reduced drawdown' if dd_sc > dd_raw else 'no DD improvement'})")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    else:
        ap.error("Real use: build_signals(events, group_map, cal, tickers) then "
                 "run(signals, ret, ...). Use --selftest here.")


if __name__ == "__main__":
    main()
