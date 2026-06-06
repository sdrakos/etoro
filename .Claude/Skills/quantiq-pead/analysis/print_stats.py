#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Win/loss distribution, positions-per-day, and the worst (losing) day breakdown
for the own-PEAD book on the 401-name universe (sector-neutral, hold=h*)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import run_pead_real as rpr

HOLD = 51
cl = pd.read_csv("prices500.csv"); cl = cl.set_index(cl.columns[0]); cl.index = pd.to_datetime(cl.index); cl = cl.sort_index()
ev = pd.read_csv("events500.csv", parse_dates=["ann_date"])
sic = json.load(open("sic500.json"))
ev = ev[ev.ticker.isin(cl.columns)]
ev = ev[(ev.ann_date >= cl.index.min()) & (ev.ann_date <= cl.index.max())].reset_index(drop=True)

AR = rpr.abnormal_returns(cl, sic)
cal = AR.index; cols = {c: i for i, c in enumerate(AR.columns)}
z_all = (ev["sue"] - ev["sue"].mean()) / (ev["sue"].std() + 1e-12)
w = np.zeros((len(cal), AR.shape[1]))
for e, row in ev.iterrows():
    j = cols.get(row["ticker"])
    if j is None: continue
    t0 = cal.searchsorted(pd.Timestamp(row["ann_date"]), side="right")
    if t0 >= len(cal): continue
    w[t0:min(t0+HOLD, len(cal)), j] += z_all.iloc[e]

active = (w != 0).sum(1)
gross = np.abs(w).sum(1, keepdims=True) + 1e-12
wn = w / gross
port = np.nansum(wn * np.nan_to_num(AR.values), axis=1)
port = pd.Series(port, index=cal)
live = port[active > 0]                      # days the book is actually on

print("=== WIN/LOSS DISTRIBUTION (own-PEAD, 401 names, 2015-2024, hold=51) ===")
print(f"trading days with book on : {len(live)}")
print(f"win days  : {(live>0).mean()*100:4.1f}%   avg win  = {live[live>0].mean()*1e4:+.1f} bp")
print(f"loss days : {(live<0).mean()*100:4.1f}%   avg loss = {live[live<0].mean()*1e4:+.1f} bp")
print(f"mean/day  : {live.mean()*1e4:+.2f} bp   median: {live.median()*1e4:+.2f} bp   std: {live.std()*1e4:.0f} bp")
print(f"best day  : {live.max()*1e4:+.0f} bp on {live.idxmax().date()}")
print(f"worst day : {live.min()*1e4:+.0f} bp on {live.idxmin().date()}")
print(f"annualized IR = {np.sqrt(252)*live.mean()/(live.std()+1e-12):.2f}")

print(f"\n=== POSITIONS PER DAY ===")
ap = pd.Series(active, index=cal)[active > 0]
print(f"median {int(ap.median())} | min {int(ap.min())} | max {int(ap.max())} names per day "
      f"(~half long / ~half short)")

# worst day breakdown
d = live.idxmin(); di = cal.get_loc(d)
contrib = wn[di] * np.nan_to_num(AR.values[di])
tab = pd.DataFrame({"ticker": list(AR.columns), "weight": wn[di],
                    "abn_ret_%": AR.values[di]*100, "contrib_bp": contrib*1e4})
tab = tab[wn[di] != 0]
print(f"\n=== WORST DAY {d.date()} ({live.min()*1e4:+.0f} bp, LOSS): biggest losers ===")
print(tab.sort_values("contrib_bp").head(6).to_string(index=False,
      formatters={'weight':'{:+.4f}'.format,'abn_ret_%':'{:+.2f}'.format,'contrib_bp':'{:+.2f}'.format}))
print("(e.g. a long that crashed, or a short that spiked, that day)")
