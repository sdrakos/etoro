#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only eToro real-price backtest of the GBT (and LSTM and fixed-rule) on the 18-asset basket.
Resolves tickers -> eToro instruments, fetches ~1000 daily candles, builds the 10 features, runs a
leak-free walk-forward, and charges REAL per-asset eToro spreads. NO orders are placed (candles +
search + rates only). Pure helpers are unit-tested; run() hits the live demo client."""
from __future__ import annotations
import sys, os
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "code"),
           os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"),
           os.path.join(HERE, "..", "..", "back")):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)
import crypto_features  # paper5/code

BASKET = ("BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD",
          "SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE")


def net_per_asset(W, fwd, spread_bps_vec, short_fin_annual=0.0):
    """W, fwd: (T,N) weights and next-bar returns. spread_bps_vec: (N,). Returns net stream (T,).
    Charges each asset's own spread on its own turnover (eToro spreads differ a lot per asset)."""
    W = np.asarray(W, float); fwd = np.asarray(fwd, float)
    gross = np.nansum(W * fwd, axis=1)
    turn = np.empty_like(W)
    turn[0] = np.abs(W[0])
    if len(W) > 1:
        turn[1:] = np.abs(W[1:] - W[:-1])
    cost = np.nansum(turn * (np.asarray(spread_bps_vec, float) / 1e4), axis=1)
    fin = (short_fin_annual / 1e4 / 252.0) * np.nansum(np.clip(-W, 0.0, None), axis=1)
    return gross - cost - fin


def panel_to_xy(close_2d, dates):
    """close_2d (T,N) + dates ['YYYY-MM-DD'] -> (X (N,T,10), fwd (N,T), dates_ms, vol (N,T causal),
    ppy, df). vol is annualised trailing-30 realized vol, shifted 1 bar (causal)."""
    idx = pd.to_datetime(dates)
    df = pd.DataFrame(np.asarray(close_2d, float), index=idx).ffill().dropna(how="all")
    X, fwd, dates_ms = crypto_features.build(df)
    days = (df.index[-1] - df.index[0]).days or 1
    ppy = len(df) / days * 365.0
    ret = df.pct_change()
    vol = (ret.rolling(30).std() * np.sqrt(ppy)).shift(1).to_numpy().T
    vol = np.nan_to_num(vol, nan=1.0)
    return X, fwd, dates_ms, vol, ppy, df


def _spread_vec(client, kept_ids):
    """Per-asset round-trip spread (bps) from live /rates bid/ask; fallback 10 bps if missing."""
    out = {iid: 10.0 for iid in kept_ids}
    try:
        rr = client.request("GET", "/api/v1/market-data/instruments/rates?instrumentIds="
                            + ",".join(str(i) for i in kept_ids))
        rates = rr.get("rates") if isinstance(rr, dict) else rr
        for it in (rates or []):
            iid = it.get("instrumentID") or it.get("instrumentId") or it.get("internalInstrumentId")
            bid = next((v for k, v in it.items() if k.lower() in ("bid", "sellrate", "sell") and isinstance(v, (int, float))), None)
            ask = next((v for k, v in it.items() if k.lower() in ("ask", "buyrate", "buy") and isinstance(v, (int, float))), None)
            if iid in out and bid and ask:
                out[iid] = (ask - bid) / ((ask + bid) / 2) * 1e4
    except Exception as e:
        print(f"[spread] fallback 10bps ({type(e).__name__})")
    return np.array([out[i] for i in kept_ids], float)


def _eval(POS, fwd, dates_ms, test_idx, band, spread_vec, ppy):
    import band_eval, metrics
    N = POS.shape[0]
    W = band_eval.apply_band(POS.T, band) / N
    F = np.asarray(fwd).T
    rows = np.asarray(test_idx)
    net = net_per_asset(W[rows], F[rows], spread_vec)
    d = np.asarray(dates_ms)[rows]
    fin = np.isfinite(net); net, d = net[fin], d[fin]
    return {"ir": metrics.ann_ir(net, ppy), "t": metrics.newey_west_t(net),
            "dsr": metrics.deflated_sharpe(net, 1, ppy), "mdd": metrics.max_drawdown(net)}


def _rule_positions(df, ppy):
    ret = df.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(ppy)
    pos = (np.sign(df.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
    return pos.ewm(span=5, min_periods=1).mean().to_numpy().T   # (N,T)


def run(tickers=BASKET):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    import train_eval, gbt_model, models
    from etoro_api.server import get_server_client
    import etoro_backtest, instrument_map
    client = get_server_client()

    def search(t):
        sym = t.replace("-USD", "")
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={sym}")
        items = r.get("items") if isinstance(r, dict) else None
        return items[0].get("internalInstrumentId") if items else None

    mapping, missing = instrument_map.resolve(list(tickers), search)
    ids = list(mapping.values()); id2tk = {v: k for k, v in mapping.items()}

    def fetch_raw(iid):
        return client.request("GET", f"/api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000")

    close, dates, kept = etoro_backtest.build_closes(fetch_raw, ids)
    print(f"[resolve] kept {len(kept)}/{len(tickers)}: {[id2tk[i] for i in kept]}  missing={missing}")
    X, fwd, dates_ms, vol, ppy, df = panel_to_xy(close, dates)
    T = X.shape[1]
    spread_vec = _spread_vec(client, kept)
    print("[spreads bps] " + ", ".join(f"{id2tk[i]}:{s:.0f}" for i, s in zip(kept, spread_vec)))
    print(f"[data] {len(kept)} assets, {T} bars, {dates[0]}..{dates[-1]}, ppy~{ppy:.0f}")

    folds = train_eval.make_folds(T, warm=126, first_train=400, step=200)
    POS_g, idx = gbt_model.gbt_positions(X, fwd, vol, folds, warm=126)
    POS_l, _, _ = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds, warm=126, epochs=300)
    POS_r = _rule_positions(df, ppy)

    rows = []
    for name, POS in [("fixed-rule", POS_r), ("LSTM-DMN", POS_l), ("GBT", POS_g)]:
        for band, tag in [(0.0, "none"), (0.3, "hard")]:
            r = _eval(POS, fwd, dates_ms, idx, band, spread_vec, ppy)
            rows.append((name, tag, r["ir"], r["t"], r["dsr"], r["mdd"]))

    print(f"\n{'model':<12}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'maxDD':>8}")
    print("-" * 50)
    for nm, bd, ir, t, dsr, mdd in rows:
        print(f"{nm:<12}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{mdd:>8.0%}")

    FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    pal = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "GBT": "#16a34a"}
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.bar(labels, irs, color=[pal[r[0]] for r in rows])
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR (real eToro prices + per-asset spreads)")
    ax.set_title(f"eToro real-price backtest — {len(kept)} assets, ~{T} bars")
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_etoro_gbt_backtest.png"), dpi=130); plt.close()
    print("\n[fig] paper5/figures/fig_etoro_gbt_backtest.png")


if __name__ == "__main__":
    run()
