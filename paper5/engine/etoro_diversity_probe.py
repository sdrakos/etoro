#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Demonstrate 'diversity > count': run the fixed-rule on 3 / 5 / 14-asset baskets over the SAME
real-eToro window and report total %, annualized %, IR, maxDD, and ENB (effective bets). Read-only."""
import sys, os
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (os.path.join(HERE, "..", "code"), os.path.join(HERE, "..", "..", "paper4", "code"),
           os.path.join(HERE, "..", "..", "paper4", "engine"), os.path.join(HERE, "..", "..", "back")):
    sys.path.insert(0, os.path.abspath(_p))
import etoro_gbt_backtest as eb
import band_eval, metrics, diversification_check as dc, etoro_backtest, instrument_map
from etoro_api.server import get_server_client

client = get_server_client()
B3 = ["SPY", "TLT", "BTC-USD"]                                 # equities / bonds / crypto
B5 = ["SPY", "TLT", "GLD", "BTC-USD", "UUP"]                   # + gold + dollar
B14 = list(eb.BASKET)                                          # whatever resolves


def search(t):
    sym = t.replace("-USD", "")
    r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={sym}")
    items = r.get("items") if isinstance(r, dict) else None
    return items[0].get("internalInstrumentId") if items else None


mapping, _ = instrument_map.resolve(B14, search)
ids = list(mapping.values()); id2tk = {v: k for k, v in mapping.items()}
close, dates, kept = etoro_backtest.build_closes(lambda iid: client.request(
    "GET", f"/api/v1/market-data/instruments/{iid}/history/candles/desc/OneDay/1000"), ids)
cols = [id2tk[i] for i in kept]
spread = {id2tk[i]: s for i, s in zip(kept, eb._spread_vec(client, kept))}
df_all = pd.DataFrame(close, index=pd.to_datetime(dates), columns=cols).ffill().dropna(how="any")
days = (df_all.index[-1] - df_all.index[0]).days or 1
ppy = len(df_all) / days * 365.0
years = days / 365.25
print(f"[window] {df_all.index[0].date()}..{df_all.index[-1].date()} ({years:.1f}y, {len(df_all)} bars), ppy~{ppy:.0f}")
print(f"\n{'basket':<8}{'n':>3}{'ENB':>6}{'total%':>9}{'/year%':>9}{'IR':>6}{'maxDD':>7}{'EUR 10k':>10}")
print("-" * 58)
for name, tks in [("B3", B3), ("B5", B5), ("B14", cols)]:
    use = [t for t in tks if t in df_all.columns]
    sub = df_all[use]
    N = sub.shape[1]
    _c, _avg, enb = dc.basket_stats(sub)
    POS = eb._rule_positions(sub, ppy)                        # (N,T)
    fwd = sub.pct_change().shift(-1).to_numpy().T            # (N,T) next-day return
    W = band_eval.apply_band(POS.T, 0.3) / N                 # hard band, equal capital
    sv = np.array([spread.get(t, 10.0) for t in use])
    net = eb.net_per_asset(W, fwd.T, sv)
    net = net[np.isfinite(net)]
    eq = float(np.prod(1.0 + net)); total = eq - 1.0; ann = eq ** (1.0 / years) - 1.0
    mdd = metrics.max_drawdown(net); ir = metrics.ann_ir(net, ppy)
    print(f"{name:<8}{N:>3}{enb:>6.1f}{total*100:>8.1f}%{ann*100:>8.1f}%{ir:>6.2f}{mdd:>7.0%}{10000*eq:>10,.0f}")
