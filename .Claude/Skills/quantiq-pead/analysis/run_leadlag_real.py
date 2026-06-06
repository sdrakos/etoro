#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real-data driver for the same-industry lead-lag (Fama-MacBeth own/peer separation).
Reuses run_pead_real's EDGAR event loader + leadlag_event_study.run.
Caches SUE events to events.csv so we don't re-pull EPS each time."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import run_pead_real as rpr
import leadlag_event_study as ll

UA = "Stefanos Drakos stefanos.drakos@gmail.com"
prices = rpr.load_prices_csv("prices.csv")
tickers = [t.strip().upper() for t in open("tickers.txt").read().split(",") if t.strip()]

if os.path.exists("events.csv"):
    events = pd.read_csv("events.csv", parse_dates=["ann_date"])
    print(f"[events] loaded {len(events)} from cache")
else:
    events = rpr.load_events_from_edgar(tickers, UA)
    events.to_csv("events.csv", index=False)
    print(f"[events] pulled {len(events)} from EDGAR -> events.csv")
events = events[events["ticker"].isin(prices.columns)].reset_index(drop=True)

group_map = ll.build_sic_map(UA, tickers)
print(f"[SIC] mapped {len(group_map)} tickers into {len(set(group_map.values()))} industry groups")
res = ll.run(prices, events, group_map, hold=60)
ll._print(res)
