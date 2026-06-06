#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Show ONE real day of the own-PEAD long-short book on the 401-name universe
(prices500.csv + events500.csv + sic500.json), sector-neutral, exactly as the engine
builds it. Prints the longs/shorts, each name's same-day abnormal return, and the P&L."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import run_pead_real as rpr
import pead_event_study as pes

HOLD = 51   # h* from the 401/2015-2024 run
cl = pd.read_csv("prices500.csv"); cl = cl.set_index(cl.columns[0]); cl.index = pd.to_datetime(cl.index); cl = cl.sort_index()
ev = pd.read_csv("events500.csv", parse_dates=["ann_date"])
sic = json.load(open("sic500.json"))
ev = ev[ev.ticker.isin(cl.columns)]
ev = ev[(ev.ann_date >= cl.index.min()) & (ev.ann_date <= cl.index.max())].reset_index(drop=True)

AR = rpr.abnormal_returns(cl, sic)                 # sector-neutral abnormal returns
cal = AR.index; cols = {c: i for i, c in enumerate(AR.columns)}
z_all = (ev["sue"] - ev["sue"].mean()) / (ev["sue"].std() + 1e-12)

# accumulate the active SUE weight per (day, ticker), exactly like calendar_time_portfolio
w = np.zeros((len(cal), AR.shape[1]))
for e, row in ev.iterrows():
    j = cols.get(row["ticker"])
    if j is None: continue
    t0 = cal.searchsorted(pd.Timestamp(row["ann_date"]), side="right")  # T+1
    if t0 >= len(cal): continue
    w[t0:min(t0+HOLD, len(cal)), j] += z_all.iloc[e]

active_per_day = (w != 0).sum(1)
# pick a rich day inside the OOS period (after 60th pct of announcements), Q4-earnings season
oos_start = ev.ann_date.quantile(0.60)
mask = (cal > oos_start) & (pd.Series(active_per_day, index=cal) > 50)
d = pd.Series(active_per_day, index=cal)[mask].idxmax()
di = cal.get_loc(d)

wd = w[di].copy(); gross = np.abs(wd).sum(); wn = wd / gross   # dollar-neutral weights
Ad = AR.values[di]                                            # sector-neutral returns that day
contrib = wn * np.nan_to_num(Ad)
tickers = list(AR.columns)
tab = pd.DataFrame({"ticker": tickers, "SUE_weight": wd, "weight": wn,
                    "abn_ret_%": Ad*100, "contrib_bp": contrib*1e4})
tab = tab[tab.SUE_weight != 0].copy()

print(f"=== Real trading day: {d.date()} (own-PEAD, sector-neutral, 401 names) ===")
print(f"active positions: {len(tab)}  ({(tab.weight>0).sum()} long / {(tab.weight<0).sum()} short)")
print(f"\nTOP 8 LONGS (best positive earnings surprises):")
print(tab.sort_values('weight', ascending=False).head(8).to_string(index=False,
      formatters={'SUE_weight':'{:+.2f}'.format,'weight':'{:+.4f}'.format,'abn_ret_%':'{:+.2f}'.format,'contrib_bp':'{:+.2f}'.format}))
print(f"\nTOP 8 SHORTS (worst negative surprises):")
print(tab.sort_values('weight').head(8).to_string(index=False,
      formatters={'SUE_weight':'{:+.2f}'.format,'weight':'{:+.4f}'.format,'abn_ret_%':'{:+.2f}'.format,'contrib_bp':'{:+.2f}'.format}))
print(f"\nDAY P&L (sum of all contributions) = {contrib.sum()*1e4:+.2f} bp  "
      f"({'WIN' if contrib.sum()>0 else 'LOSS'} that day)")
print("interpretation: longs that went UP (+abn_ret) and shorts that went DOWN (-abn_ret) add positive bp.")
