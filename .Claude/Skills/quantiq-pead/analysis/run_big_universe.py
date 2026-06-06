#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run own-PEAD + same-industry lead-lag on a large universe. One EDGAR pull
(events{tag}.csv + sic{tag}.json caches) feeds both. Sector-neutral own-PEAD uses the
EDGAR SIC map. Distinct output prefixes per --tag so prior runs stay intact.

  python run_big_universe.py                       # 470 S&P (2013-2018) from sp500_5yr.csv
  python run_big_universe.py --prices prices500.csv --tag 500   # custom wide panel
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import run_pead_real as rpr
import leadlag_event_study as ll

UA = "Stefanos Drakos stefanos.drakos@gmail.com"
HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--prices", help="wide csv (date x ticker); default builds from sp500_5yr.csv")
ap.add_argument("--tag", default="470", help="suffix for caches + outputs")
ap.add_argument("--hold", type=int, default=60)
a = ap.parse_args()

# 1) wide price panel
if a.prices:
    cl = pd.read_csv(os.path.join(HERE, a.prices))
    cl = cl.set_index(cl.columns[0]); cl.index = pd.to_datetime(cl.index); cl = cl.sort_index()
else:
    sp = os.path.join(HERE, "..", "..", "..", "..", "paper1_RL", "sp500_5yr.csv")
    raw = pd.read_csv(sp)
    cl = raw.pivot(index="date", columns="Name", values="close").sort_index()
    cl = cl[cl.columns[cl.notna().all()]]; cl.index = pd.to_datetime(cl.index)
tickers = list(cl.columns)
print(f"[prices] {cl.shape[0]} days x {len(tickers)} tickers ({cl.index[0].date()} -> {cl.index[-1].date()})")

# 2) EDGAR SUE events (cache)
ev_cache = os.path.join(HERE, f"events{a.tag}.csv")
if os.path.exists(ev_cache):
    events = pd.read_csv(ev_cache, parse_dates=["ann_date"]); print(f"[events] loaded {len(events)} from cache")
else:
    events = rpr.load_events_from_edgar(tickers, UA)
    events = events.drop_duplicates(["ticker", "ann_date"]).dropna(subset=["sue"])
    events.to_csv(ev_cache, index=False); print(f"[events] pulled {len(events)} from EDGAR -> {os.path.basename(ev_cache)}")
events = events[events["ticker"].isin(cl.columns)]
events = events[(events["ann_date"] >= cl.index.min()) &
                (events["ann_date"] <= cl.index.max())].reset_index(drop=True)
print(f"[events] {len(events)} within price window {cl.index.min().date()}..{cl.index.max().date()}")

# 3) EDGAR SIC industry map (cache)
sic_cache = os.path.join(HERE, f"sic{a.tag}.json")
if os.path.exists(sic_cache):
    sic = json.load(open(sic_cache)); print(f"[SIC] loaded {len(sic)} from cache")
else:
    sic = ll.build_sic_map(UA, tickers); json.dump(sic, open(sic_cache, "w"))
print(f"[SIC] {len(sic)} tickers in {len(set(sic.values()))} industry groups")

# 4) own-firm PEAD (sector-neutral via SIC) ; 5) same-industry lead-lag
print(f"\n=== OWN-FIRM PEAD ({a.tag}, sector-neutral) ===")
rpr._print(rpr.run(cl, events, sector_map=sic, hold=a.hold, outprefix=f"pead_real{a.tag}"))
print(f"\n=== SAME-INDUSTRY LEAD-LAG ({a.tag}) ===")
ll._print(ll.run(cl, events, sic, hold=a.hold, outprefix=f"leadlag{a.tag}"))
