#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report ACTUAL cumulative returns (not just IR) of the GBT and fixed-rule on real eToro prices.
Reuses the tested helpers from etoro_gbt_backtest. Read-only (candles+search+rates). Skips the LSTM
for speed. Prints total %, annualized %, and EUR on a 10,000 EUR notional."""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (os.path.join(HERE, "..", "code"), os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"), os.path.join(HERE, "..", "..", "back")):
    sys.path.insert(0, os.path.abspath(_p))
import etoro_gbt_backtest as eb
import train_eval, gbt_model, band_eval, etoro_backtest, instrument_map
from etoro_api.server import get_server_client

client = get_server_client()


def search(t):
    sym = t.replace("-USD", "")
    r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={sym}")
    items = r.get("items") if isinstance(r, dict) else None
    return items[0].get("internalInstrumentId") if items else None


mapping, missing = instrument_map.resolve(list(eb.BASKET), search)
ids = list(mapping.values()); id2tk = {v: k for k, v in mapping.items()}
close, dates, kept = etoro_backtest.build_closes(lambda iid: client.request(
    "GET", f"/api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000"), ids)
X, fwd, dates_ms, vol, ppy, df = eb.panel_to_xy(close, dates)
T = X.shape[1]; N = X.shape[0]
spread = eb._spread_vec(client, kept)
folds = train_eval.make_folds(T, warm=126, first_train=400, step=200)
POS_g, idx = gbt_model.gbt_positions(X, fwd, vol, folds, warm=126)
POS_r = eb._rule_positions(df, ppy)
years = (np.asarray(dates_ms)[idx][-1] - np.asarray(dates_ms)[idx][0]) / 1000 / 86400 / 365.25
print(f"[period] {dates[idx[0]]}..{dates[idx[-1]]}  ({years:.1f} years, {len(idx)} test bars, {N} assets)")
print(f"\n{'model':<11}{'band':<6}{'total%':>9}{'/year%':>9}{'IR':>6}{'EUR on 10k':>13}")
print("-" * 54)
for name, POS in [("fixed-rule", POS_r), ("GBT", POS_g)]:
    for band, tag in [(0.0, "none"), (0.3, "hard")]:
        W = band_eval.apply_band(POS.T, band) / N
        net = eb.net_per_asset(W[idx], fwd.T[idx], spread)
        net = net[np.isfinite(net)]
        eq = float(np.prod(1.0 + net))
        total = eq - 1.0
        ann = eq ** (1.0 / years) - 1.0
        import metrics
        print(f"{name:<11}{tag:<6}{total*100:>8.1f}%{ann*100:>8.1f}%{metrics.ann_ir(net, ppy):>6.2f}"
              f"{10000*eq:>12,.0f}")
