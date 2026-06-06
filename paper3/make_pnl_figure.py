#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real PnL / equity curve of the own-PEAD long-short book (401 names, 2015-2024).
Gross and net-of-cost cumulative NAV + drawdown. Honest: shows the razor-thin edge."""
import sys, os, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ETORO = os.path.abspath(os.path.join(HERE, ".."))
ANA = os.path.join(ETORO, ".Claude", "Skills", "quantiq-pead", "analysis")
sys.path.insert(0, ANA)
import run_pead_real as rpr
FIG = os.path.join(HERE, "figures"); os.makedirs(FIG, exist_ok=True)
SPREAD, HOLD = 5e-4, 51

cl = pd.read_csv(os.path.join(ANA, "prices500.csv"), index_col=0, parse_dates=True).sort_index()
ev = pd.read_csv(os.path.join(ANA, "events500.csv"), parse_dates=["ann_date"])
sic = json.load(open(os.path.join(ANA, "sic500.json")))
ev = ev[ev.ticker.isin(cl.columns)]
ev = ev[(ev.ann_date >= cl.index.min()) & (ev.ann_date <= cl.index.max())].reset_index(drop=True)
AR = rpr.abnormal_returns(cl.ffill(), sic); cal = AR.index; T = len(cal)
cols = {c: i for i, c in enumerate(AR.columns)}
z = (ev["sue"] - ev["sue"].mean()) / (ev["sue"].std() + 1e-12)
w = np.zeros((T, AR.shape[1]))
for e, r in ev.iterrows():
    j = cols.get(r["ticker"]);
    if j is None: continue
    t0 = cal.searchsorted(pd.Timestamp(r["ann_date"]), side="right")
    if t0 >= T: continue
    w[t0:min(t0 + HOLD, T), j] += z.iloc[e]
wn = w / (np.abs(w).sum(1, keepdims=True) + 1e-12)
turn = np.abs(np.diff(wn, axis=0, prepend=0)).sum(1)
gross = np.nansum(wn * np.nan_to_num(AR.values), axis=1)
net = gross - SPREAD * turn
sl = slice(252, T)                                   # drop warmup
g, n_, dts = gross[sl], net[sl], cal[sl]
splitdate = ev["ann_date"].quantile(0.60)            # train/test boundary

def nav(x): return np.cumprod(1 + x)
def dd(x):
    eq = nav(x); return eq / np.maximum.accumulate(eq) - 1
def ir(x): return np.sqrt(252) * x.mean() / (x.std() + 1e-12)

fig, ax = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
ax[0].plot(dts, nav(g), color="#16a34a", lw=1.7, label=f"gross (IR {ir(g):.2f}, ret {nav(g)[-1]-1:+.0%})")
ax[0].plot(dts, nav(n_), color="#1f5fa8", lw=1.7, label=f"net of 5bps (IR {ir(n_):.2f}, ret {nav(n_)[-1]-1:+.0%})")
ax[0].axvline(splitdate, color="k", ls=":", lw=1, alpha=.6); ax[0].text(splitdate, ax[0].get_ylim()[0], " OOS →", fontsize=8, va="bottom")
ax[0].axhline(1, color="k", lw=.6); ax[0].set_ylabel("Net asset value"); ax[0].legend(loc="upper left")
ax[0].set_title("own-PEAD long-short book: real PnL (401 names, 2015-2024, sector-neutral)")
ax[0].grid(alpha=.3)
ax[1].fill_between(dts, dd(n_) * 100, 0, color="#dc2626", alpha=.5)
ax[1].set_ylabel("Drawdown %"); ax[1].set_xlabel("date"); ax[1].grid(alpha=.3)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_pnl.png"), dpi=130); plt.close()
print(f"[fig] fig_pnl.png | gross ret {nav(g)[-1]-1:+.1%} IR {ir(g):.2f} | "
      f"net ret {nav(n_)[-1]-1:+.1%} IR {ir(n_):.2f} maxDD {dd(n_).min():.1%}")
