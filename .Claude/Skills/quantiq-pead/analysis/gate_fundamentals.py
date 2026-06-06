#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the fundamental factors (from fundamentals_api) through the SAME Fundamental-Law
gate used for own-PEAD, on the 401-name panel (prices500, 2015-2024). Theory-driven signs
(no sign-fitting). Prints IC / NW-t / realized-IR per factor: which pass |t|>2."""
import sys, os, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ETORO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ETORO, ".Claude", "Skills", "quantiq-pead", "skill", "sec-edgar", "scripts"))
sys.path.insert(0, os.path.join(ETORO, "paper1_RL"))
import fundamentals_api as FA
from fundamentals_loader import to_pointintime_daily
from alpha_gate import evaluate                                  # same gate as own-PEAD

UA = "Stefanos Drakos stefanos.drakos@gmail.com"
cl = pd.read_csv(os.path.join(HERE, "prices500.csv"), index_col=0, parse_dates=True).sort_index()
cal = cl.index; tickers = list(cl.columns)
closeM = cl.ffill().values.astype(float)

# 1) fundamentals (cache the slow EDGAR pull)
CACHE = os.path.join(HERE, "fundamentals500.csv")
if os.path.exists(CACHE):
    panel = pd.read_csv(CACHE, parse_dates=["end", "filed"])
    print(f"[fund] loaded {len(panel)} rows from cache")
else:
    panel = FA.get_fundamentals(UA, tickers)
    panel.to_csv(CACHE, index=False)
    print(f"[fund] pulled {len(panel)} rows -> {os.path.basename(CACHE)}")
fac = FA.fundamental_factors(panel)

def daily(colseries_panel, col):
    """PiT daily (date x ticker) aligned to close, for one factor column."""
    p = colseries_panel.dropna(subset=["filed", col])[["ticker", "filed", col]]
    d = to_pointintime_daily(p.rename(columns={col: "val"}), cal, value_col="val")
    return d.reindex(index=cal, columns=tickers)

# 2) signals with THEORY signs (higher = predicted higher return)
sigs = {
    "gross_profits_to_assets": (+1, "quality"),
    "accruals":               (-1, "low accruals = quality"),
    "asset_growth_yoy":       (-1, "investment factor"),
    "net_margin":             (+1, "profitability"),
    "roe":                    (+1, "profitability"),
    "operating_margin":       (+1, "profitability"),
    "debt_to_equity":         (-1, "low leverage"),
    "shares_yoy":             (-1, "buyback"),
}
# value factor needs price: book-to-price = equity / (price * shares_out)
eq_d = daily(fac, "equity"); sh_d = daily(fac, "shares_out")
mktcap = cl.reindex(columns=tickers).values * sh_d.values
bp = np.where(mktcap > 0, eq_d.values / mktcap, np.nan)

# pre-build factor matrices once
mats = {name: sign * daily(fac, name).values for name, (sign, _n) in sigs.items()}
mats["book_to_price"] = bp

for HOLD in (63, 126, 252):
    print(f"\n=== hold = {HOLD} trading days ({ {63:'quarterly',126:'semiannual',252:'annual'}[HOLD] }) ===")
    print(f"{'factor':<26}{'IC':>9}{'NW t':>8}{'realIR':>9}  gate")
    print("-" * 62)
    for name, M in mats.items():
        r = evaluate(signal=M, close=closeM, hold=HOLD)
        tag = "PASS" if abs(r["IC_t"]) > 2 else "reject"
        print(f"{name:<26}{r['IC']:>9.4f}{r['IC_t']:>8.2f}{r['realIR']:>9.2f}  {tag}  (n={r['n']})")
print("\nPASS = |IC t| > 2 (theory-signed, OOS). Longer hold = the natural horizon for slow fundamentals.")
