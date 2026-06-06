#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate paper3 figures into paper3/figures/ from the cached real-data runs.
  fig_drift.png        : own-PEAD drift profile b(k), cumulative B(h), durability by year (401)
  fig_crossconfig.png  : own-PEAD vs lead-lag t-stat across the 3 universes (the fragility result)
  fig_fundamentals.png : |IC t| of the 9 theory-signed fundamental factors vs the |t|=2 gate
"""
import sys, os, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ETORO = os.path.abspath(os.path.join(HERE, ".."))
ANA = os.path.join(ETORO, ".Claude", "Skills", "quantiq-pead", "analysis")
sys.path.insert(0, ANA)
sys.path.insert(0, os.path.join(ETORO, ".Claude", "Skills", "quantiq-pead", "skill", "sec-edgar", "scripts"))
import run_pead_real as rpr, pead_event_study as pes
FIG = os.path.join(HERE, "figures"); os.makedirs(FIG, exist_ok=True)
BLUE, RED, GREEN, GRAY = "#1f5fa8", "#dc2626", "#16a34a", "#888888"

# ---- own-PEAD drift profile + durability on the 401 panel ----
cl = pd.read_csv(os.path.join(ANA, "prices500.csv"), index_col=0, parse_dates=True).sort_index()
ev = pd.read_csv(os.path.join(ANA, "events500.csv"), parse_dates=["ann_date"])
sic = json.load(open(os.path.join(ANA, "sic500.json")))
ev = ev[ev.ticker.isin(cl.columns)]
ev = ev[(ev.ann_date >= cl.index.min()) & (ev.ann_date <= cl.index.max())].reset_index(drop=True)
AR = rpr.abnormal_returns(cl.ffill(), sic)
b, B, kax, n = pes.drift_profile(ev, AR, hold=60)
hstar = int(np.argmax(B) + 1)
dur = pes.durability_by_year(pes.calendar_time_portfolio(ev, AR, hold=hstar))

fig, ax = plt.subplots(1, 3, figsize=(14, 4))
ax[0].bar(kax, b * 1e4, color=BLUE, alpha=.75); ax[0].axhline(0, color="k", lw=.6)
ax[0].set_title("Marginal drift per unit SUE"); ax[0].set_xlabel("days after entry"); ax[0].set_ylabel("bp/day")
ax[1].plot(kax + 1, B * 100, color=BLUE, lw=1.8); ax[1].axvline(hstar, color=RED, ls="--", label=f"h*={hstar}")
ax[1].axhline(0, color="k", lw=.6); ax[1].set_title("Cumulative drift B(h) per unit SUE")
ax[1].set_xlabel("holding days"); ax[1].set_ylabel("%"); ax[1].legend()
ax[2].bar(dur["year"], dur["IR"], color=GREEN, alpha=.8); ax[2].axhline(0, color="k", lw=.6)
ax[2].set_title("Durability: own-PEAD IR by year"); ax[2].set_xlabel("year"); ax[2].set_ylabel("IR")
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_drift.png"), dpi=130); plt.close()
print("[fig] fig_drift.png  (h*=%d, b1=%.2fbp)" % (hstar, b[0]*1e4))

# ---- cross-config fragility: t-stats across universes ----
labels = ["150 mega-cap\n2015-24", "470 broad\n2013-18", "401 broad\n2015-24"]
pead_t = [1.20, 0.61, 2.54]; ll_t = [2.61, 1.89, 0.10]
x = np.arange(3); w = 0.38
fig, axx = plt.subplots(figsize=(7.5, 4.3))
axx.bar(x - w/2, pead_t, w, label="own-PEAD", color=BLUE, alpha=.85)
axx.bar(x + w/2, ll_t, w, label="lead-lag (clean)", color=RED, alpha=.85)
axx.axhline(2.0, color="k", ls="--", lw=1.2); axx.text(2.05, 2.06, "gate: |t|>2", fontsize=9)
axx.set_xticks(x); axx.set_xticklabels(labels); axx.set_ylabel("Newey-West t-stat (OOS)")
axx.set_title("Signals are universe-dependent: significance flips with the universe")
axx.legend(); axx.grid(axis="y", alpha=.3)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_crossconfig.png"), dpi=130); plt.close()
print("[fig] fig_crossconfig.png")

# ---- fundamentals: |IC t| vs gate (all fail) ----
fac = ["gross-prof/assets", "accruals", "asset growth", "net margin", "ROE",
       "op. margin", "debt/equity", "buyback", "book/price"]
t = [0.61, 0.29, 1.11, 1.03, 0.55, 0.87, 0.87, 0.51, 0.85]
fig, axf = plt.subplots(figsize=(8.5, 4))
axf.bar(fac, t, color=GRAY, alpha=.85, edgecolor="k", lw=.4)
axf.axhline(2.0, color=RED, ls="--", lw=1.3); axf.text(0, 2.05, "gate: |t|>2", color=RED, fontsize=9)
axf.set_ylim(0, 2.4); axf.set_ylabel("|IC t-stat| (OOS, monthly)")
axf.set_title("Fundamental factors: none clears the gate (theory-signed, 401 names)")
plt.setp(axf.get_xticklabels(), rotation=30, ha="right"); axf.grid(axis="y", alpha=.3)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_fundamentals.png"), dpi=130); plt.close()
print("[fig] fig_fundamentals.png")
