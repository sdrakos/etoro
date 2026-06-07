#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real equity curve + drawdown of the crypto banded-daily momentum (the config with net IR 1.27).
Annotates IR / Newey-West t / maxDD and shades 2022. Figure for the tests tutorial."""
import sys, os
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import yfinance as yf

CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD"]
FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)


def fetch_daily(tickers, period="13y"):
    df = yf.download(tickers, period=period, interval="1d", auto_adjust=True, progress=False, group_by="ticker")
    cols = {}
    for t in tickers:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 300: cols[t] = s
        except Exception: pass
    return pd.DataFrame(cols).sort_index()


def apply_band(pos, band):
    T, N = pos.shape; held = np.zeros_like(pos); cur = np.zeros(N)
    for t in range(T):
        upd = np.abs(pos[t] - cur) > band
        cur = np.where(upd, pos[t], cur); held[t] = cur
    return held


close = fetch_daily(CRYPTO).ffill().dropna(how="all")
days = (close.index[-1] - close.index[0]).days or 1
ppy = len(close) / days * 365.0
ret = close.pct_change()
vol = ret.rolling(30).std() * np.sqrt(ppy)
pos = (np.sign(close.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
pos = pos.ewm(span=5, min_periods=1).mean()
W = apply_band(pos.values, 0.3) / close.shape[1]
fwd = ret.shift(-1).values
m = np.isfinite(fwd).all(axis=1)
W, F, idx = W[m], fwd[m], close.index[m]
net = costs.net_returns(W, F, 10.0, 0.0)
fin = np.isfinite(net); net, idx = net[fin], idx[fin]

eq = np.cumprod(1 + net)
dd = eq / np.maximum.accumulate(eq) - 1.0
IR = metrics.ann_ir(net, ppy); t = metrics.newey_west_t(net); mdd = dd.min()

fig, ax = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
ax[0].plot(idx, eq, color="#16a34a", lw=1.6)
ax[0].set_yscale("log"); ax[0].set_ylabel("equity (log, start=1)")
ax[0].axvspan(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"), color="#dc2626", alpha=.12)
ax[0].text(pd.Timestamp("2022-02-01"), eq.max()*0.6, "2022 crash\n(BTC -65%)", fontsize=8, color="#dc2626")
ax[0].set_title(f"Crypto banded-daily momentum (net @10bps): IR {IR:.2f} | NW-t {t:.2f} | maxDD {mdd:.0%}")
ax[0].grid(alpha=.3, which="both")
ax[1].fill_between(idx, dd*100, 0, color="#dc2626", alpha=.5)
ax[1].axvspan(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"), color="#dc2626", alpha=.12)
ax[1].set_ylabel("drawdown %"); ax[1].set_xlabel("date"); ax[1].grid(alpha=.3)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_crypto_pnl.png"), dpi=130); plt.close()
print(f"[fig] fig_crypto_pnl.png | IR {IR:.2f} | NW-t {t:.2f} | maxDD {mdd:.1%} | "
      f"total {eq[-1]-1:+.0%} over {idx[0].date()}..{idx[-1].date()}")
