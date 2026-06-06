"""Backtest the paper4 rules strategy on REAL eToro daily prices for a chosen product set.

eToro daily candles reach ~1000 bars (~4 years), enough for a real-price validation backtest
(not the 17-year study). Pure helpers (parse_candles, build_closes) are unit-tested; run() hits
the live eToro client. CLI: python paper4/engine/etoro_backtest.py [TICKER ...]
"""
from __future__ import annotations
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE,
           os.path.abspath(os.path.join(HERE, "..", "code")),
           os.path.abspath(os.path.join(HERE, "..", "..", "Strategies", "slow-momentum-fast-reversion")),
           os.path.abspath(os.path.join(HERE, "..", "..", "back"))):   # for etoro_api.*
    if _p not in sys.path:
        sys.path.insert(0, _p)
from ts_momentum import build_ts_weights        # noqa: E402
from costs import net_returns                    # noqa: E402
from metrics import ann_ir, max_drawdown         # noqa: E402

DEFAULT = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "LQD", "HYG",
           "GLD", "SLV", "USO", "UUP", "VNQ", "XLE", "XLF", "XLK"]


def parse_candles(raw):
    """eToro candle response -> [(date 'YYYY-MM-DD', close)] ascending."""
    groups = (raw or {}).get("candles") or []
    inner = (groups[0].get("candles") if groups else []) or []
    out = [(c["fromDate"][:10], float(c["close"])) for c in inner if c.get("close") is not None]
    return sorted(out)


def build_closes(fetch_raw, instrument_ids):
    """fetch_raw(id)->candle response. Returns (close (T,N), dates, ids_kept) on a common grid."""
    series = {}
    for iid in instrument_ids:
        s = dict(parse_candles(fetch_raw(iid)))
        if len(s) > 300:
            series[iid] = s
    ids = [i for i in instrument_ids if i in series]
    all_dates = sorted(set().union(*[set(series[i]) for i in ids])) if ids else []
    close = np.full((len(all_dates), len(ids)), np.nan)
    idx = {d: k for k, d in enumerate(all_dates)}
    for j, iid in enumerate(ids):
        for d, c in series[iid].items():
            close[idx[d], j] = c
    return close, all_dates, ids


def _ffill(close):
    out = close.copy()
    for j in range(out.shape[1]):
        last = np.nan
        for i in range(len(out)):
            if np.isnan(out[i, j]):
                out[i, j] = last
            else:
                last = out[i, j]
    return out


def backtest_rules(close, capital=10000.0, target_vol=0.10, long_only=False):
    """Rules time-series momentum on a (T,N) close matrix, net of 5bps. Returns dict + equity.
    target_vol is the risk dial (the return stream is scaled to this annual volatility);
    long_only=True keeps only the up-trends (drops the short legs)."""
    close = _ffill(close)
    T, N = close.shape
    W = build_ts_weights(close)
    if long_only:
        W = np.clip(W, 0.0, None)
    fwd = np.zeros((T, N)); fwd[:-1] = close[1:] / close[:-1] - 1.0
    net = net_returns(W, fwd, spread_bps=5.0, short_fin_bps_annual=0.0)
    warm = 252
    a = net[warm:T - 1]
    a = a * (target_vol / (a.std() * np.sqrt(252) + 1e-12))
    eq = capital * np.cumprod(1 + a)
    return {"ir": ann_ir(a), "sharpe": float(a.mean() / a.std() * np.sqrt(252)),
            "maxdd": max_drawdown(a), "final": float(eq[-1]), "n_days": len(a)}, a, eq


def run(tickers=None, capital=10000.0, target_vol=0.10, long_only=False):
    import json
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from etoro_api.server import get_server_client
    tickers = tickers or DEFAULT
    client = get_server_client()

    def search(t):
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={t}")
        ex = [x for x in (r or {}).get("items", [])
              if x.get("internalSymbolFull") == t and not x.get("isHiddenFromClient", False)]
        return int(ex[0]["instrumentId"]) if ex else None

    ids, id2tk, missing = [], {}, []
    for t in tickers:
        iid = search(t)
        if iid:
            ids.append(iid); id2tk[iid] = t
        else:
            missing.append(t)
    if missing:
        print(f"[warn] not on eToro: {missing}")

    def fetch_raw(iid):
        return client.request(
            "GET", f"/api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000")

    close, dates, kept = build_closes(fetch_raw, ids)
    print(f"eToro prices: {len(kept)} products, {len(dates)} days ({dates[0]}..{dates[-1]})")
    stats, _ret, eq = backtest_rules(close, capital=capital, target_vol=target_vol, long_only=long_only)
    mode = "long-only" if long_only else "long/short"
    print(f"\n=== eToro-prices backtest (rules, {mode}, net, {target_vol*100:.0f}% vol target) ===")
    print(f"  period   {dates[252]}..{dates[-2]}")
    print(f"  IR {stats['ir']:+.2f}   Sharpe {stats['sharpe']:.2f}   maxDD {stats['maxdd']*100:+.0f}%"
          f"   final EUR {stats['final']:,.0f}  (from {capital:,.0f})")

    FIG = os.path.abspath(os.path.join(HERE, "..", "figures"))
    plt.rcParams.update({"font.family": "serif", "figure.dpi": 150, "savefig.bbox": "tight"})
    d = [np.datetime64(x) for x in dates[252:len(eq) + 252]]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), height_ratios=[2, 1], sharex=True)
    ax1.plot(d, eq, color="#1f4e9c", lw=2)
    ax1.set_ylabel("Account value (EUR)"); ax1.grid(alpha=.3)
    ax1.set_title(f"eToro real-price backtest (rules) — {len(kept)} products, "
                  f"IR {stats['ir']:+.2f}, maxDD {stats['maxdd']*100:.0f}%")
    peak = np.maximum.accumulate(eq); dd = (eq / peak - 1) * 100
    ax2.fill_between(d, dd, 0, color="#c0392b", alpha=.5)
    ax2.set_ylabel("Drawdown %"); ax2.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_etoro_backtest.png")); plt.close(fig)
    with open(os.path.join(HERE, "..", "results_etoro_backtest.json"), "w", encoding="utf-8") as f:
        json.dump({"products": [id2tk[i] for i in kept], "period": [dates[252], dates[-2]], **stats}, f, indent=2)
    print("\nSaved figures/fig_etoro_backtest.png + results_etoro_backtest.json")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Backtest the rules strategy on real eToro daily prices.")
    ap.add_argument("tickers", nargs="*", help="product tickers (default: a diversified 17-ETF set)")
    ap.add_argument("--vol", type=float, default=0.10, help="risk dial: target annual volatility (e.g. 0.20)")
    ap.add_argument("--capital", type=float, default=10000.0)
    ap.add_argument("--long-only", action="store_true", help="keep only up-trends (drop the shorts)")
    a = ap.parse_args()
    run(a.tickers or None, capital=a.capital, target_vol=a.vol, long_only=a.long_only)
