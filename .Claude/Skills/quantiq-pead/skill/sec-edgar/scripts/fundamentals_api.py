#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fundamentals_api.py — ONE endpoint that returns ALL the key fundamentals for a set of
tickers, point-in-time, from SEC EDGAR (free, no API key).

    from fundamentals_api import get_fundamentals, fundamental_factors
    panel   = get_fundamentals("Name email@x.com", ["AAPL","MSFT"])   # raw line items
    factors = fundamental_factors(panel)                              # derived signals

`get_fundamentals` pulls each concept via the EDGAR XBRL companyconcept API and merges
them into ONE tidy per-(ticker, fiscal-period) table, keyed for point-in-time use by the
`filed` date (the day the figure became public — never the period end, so no look-ahead).

`fundamental_factors` is a PURE function (no IO): it derives the standard cross-sectional
factors (margins, quality, accruals, investment, leverage, FCF, buyback) from that table.
Price-dependent factors (book-to-price, earnings yield) are left to the caller, who has prices.

None of these is strong alone; the edge (if any) is in combining several orthogonal ones via
risk parity, after passing the gate net-of-costs and surviving CPCV / Deflated Sharpe.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from edgar_client import EdgarClient
from fundamentals_loader import load_concept_panel

# the line items the endpoint returns by default (keys of TAG_FALLBACKS in fundamentals_loader)
DEFAULT_CONCEPTS = ["revenue", "net_income", "gross_profit", "operating_income",
                    "assets", "equity", "long_term_debt", "cash",
                    "operating_cf", "capex", "shares_out"]


def get_fundamentals(user_agent_or_client, tickers, concepts=None,
                     forms=("10-Q", "10-K"), keep="first_filed"):
    """Consolidated point-in-time fundamentals panel.

    Returns one row per (ticker, fiscal period `end`) with columns:
        ticker, fy, fp, end, filed, <one column per concept>
    `filed` is the LATEST filing date among the merged concepts (conservative PiT: the day
    all of that period's figures were public). Pass a User-Agent string OR an EdgarClient.
    """
    ec = user_agent_or_client if isinstance(user_agent_or_client, EdgarClient) \
        else EdgarClient(user_agent_or_client)
    concepts = concepts or DEFAULT_CONCEPTS

    merged = None
    for c in concepts:
        df = load_concept_panel(ec, tickers, c, forms=forms, keep=keep)
        if df.empty:
            continue
        df = (df[["ticker", "end", "fy", "fp", "val", "filed"]]
              .rename(columns={"val": c, "filed": f"filed__{c}"}))
        merged = df if merged is None else merged.merge(
            df, on=["ticker", "end", "fy", "fp"], how="outer")
    if merged is None:
        return pd.DataFrame()

    filed_cols = [x for x in merged.columns if x.startswith("filed__")]
    merged["filed"] = merged[filed_cols].max(axis=1)        # PiT: when all were public
    merged = merged.drop(columns=filed_cols)
    front = ["ticker", "fy", "fp", "end", "filed"]
    rest = [c for c in merged.columns if c not in front]
    return merged[front + rest].sort_values(["ticker", "end"]).reset_index(drop=True)


def fundamental_factors(panel):
    """PURE: derive cross-sectional factors from a get_fundamentals() panel.
    Adds columns; YoY uses 4 quarters within ticker (sorted by period end)."""
    df = panel.sort_values(["ticker", "end"]).copy()

    def col(name):
        return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)

    rev, ni, gp = col("revenue"), col("net_income"), col("gross_profit")
    oi, assets, eq = col("operating_income"), col("assets"), col("equity")
    ltd, ocf, capex = col("long_term_debt"), col("operating_cf"), col("capex")
    sh = col("shares_out")

    df["net_margin"] = ni / rev.replace(0, np.nan)
    df["operating_margin"] = oi / rev.replace(0, np.nan)
    df["gross_profits_to_assets"] = gp / assets.replace(0, np.nan)      # Novy-Marx quality
    df["fcf"] = ocf - capex
    df["accruals"] = (ni - ocf) / assets.replace(0, np.nan)            # low = higher quality
    df["debt_to_equity"] = ltd / eq.replace(0, np.nan)
    df["roe"] = ni / eq.replace(0, np.nan)
    g = df.groupby("ticker", group_keys=False)
    df["asset_growth_yoy"] = (g["assets"].apply(lambda s: s.pct_change(4))     # investment factor
                              if "assets" in df.columns else np.nan)
    df["shares_yoy"] = (g["shares_out"].apply(lambda s: s.pct_change(4))       # <0 = buyback (bullish)
                        if "shares_out" in df.columns else np.nan)
    return df


if __name__ == "__main__":
    import sys
    ua = sys.argv[1] if len(sys.argv) > 1 else "Example User example@example.com"
    p = get_fundamentals(ua, ["AAPL", "MSFT"])
    f = fundamental_factors(p)
    cols = ["ticker", "fp", "end", "filed", "revenue", "net_income",
            "gross_profits_to_assets", "accruals", "asset_growth_yoy"]
    print(f[[c for c in cols if c in f.columns]].tail(8).to_string(index=False))
