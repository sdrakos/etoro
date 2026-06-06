#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fundamentals_loader.py — turn EDGAR concepts into a POINT-IN-TIME panel across many tickers.

Two outputs you will actually use:
  load_concept_panel(...)  -> long tidy table [ticker, end, fp, val, filed, form]
  to_pointintime_daily(...) -> wide daily (date x ticker) frame, each value active from its
                               FILING date (no look-ahead), forward-filled until the next filing.

The 'filed' date is the key to honesty: a fundamental only becomes usable on the day it was
filed, so aligning on 'filed' (not the period end) is what makes the series backtest-safe.

EPS note: 10-Q gives Q1-Q3 quarterly EPS directly; Q4 is not filed as a quarter, so it is
derived as FY (from the 10-K) minus the first three quarters. EPS is only approximately
additive (share counts drift), so for rigorous work prefer NetIncomeLoss / shares. Both
paths are provided.
"""

import time
import pandas as pd
from edgar_client import EdgarClient

# Common tag fallbacks (companies are inconsistent about which XBRL tag they use)
TAG_FALLBACKS = {
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "eps_basic": ["EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"],
    "net_income": ["NetIncomeLoss", "ProfitLoss",
                   "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"],
    "assets": ["Assets"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}


def _first_available(ec, ticker, candidates, **kw):
    for tag in candidates:
        df = ec.concept_series(ticker, tag, **kw)
        if df is not None and len(df):
            df = df.copy()
            df["tag"] = tag
            return df
    return pd.DataFrame()


def load_concept_panel(ec, tickers, concept="eps_diluted",
                       forms=("10-Q", "10-K"), keep="first_filed", pause=0.0):
    """
    Pull one concept across many tickers into a long tidy panel.

    concept: a key of TAG_FALLBACKS, or a raw XBRL tag string.
    Returns columns: ticker, end, fp, fy, val, filed, form, tag.
    """
    candidates = TAG_FALLBACKS.get(concept, [concept])
    frames = []
    for t in tickers:
        try:
            df = _first_available(ec, t, candidates, forms=forms, keep=keep)
        except KeyError:
            continue  # unknown ticker
        if len(df):
            df.insert(0, "ticker", t.upper())
            frames.append(df)
        if pause:
            time.sleep(pause)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    cols = [c for c in ["ticker", "end", "fp", "fy", "val", "filed", "form", "tag"]
            if c in out.columns]
    return out[cols].sort_values(["ticker", "end"]).reset_index(drop=True)


def to_pointintime_daily(panel, calendar, value_col="val"):
    """
    Convert a long panel [ticker, filed, val] into a wide daily (date x ticker) frame,
    where each ticker's value steps to the new figure on its FILING date and holds until
    the next filing. 'calendar' is a DatetimeIndex (e.g. your trading days).

    This is the bridge from sparse quarterly fundamentals to your daily price series.
    """
    calendar = pd.DatetimeIndex(calendar).sort_values()
    wide = {}
    for tk, g in panel.dropna(subset=["filed"]).groupby("ticker"):
        s = (g.sort_values("filed")
               .drop_duplicates(subset=["filed"], keep="last")
               .set_index("filed")[value_col])
        # place each value on its filing date, then forward-fill across the calendar
        wide[tk] = s.reindex(s.index.union(calendar)).ffill().reindex(calendar)
    return pd.DataFrame(wide, index=calendar)


def quarterly_eps(ec, tickers, keep="first_filed", derive_q4=True):
    """
    Build a clean quarterly EPS panel suitable for SUE/PEAD.

    Q1-Q3 come straight from 10-Q. Q4 (if derive_q4) = FY 10-K EPS minus (Q1+Q2+Q3) of
    the same fiscal year. Adds a 'quarter_end' and keeps 'filed' for point-in-time use.
    Returns: ticker, fy, fp, end, eps, filed.
    """
    raw = load_concept_panel(ec, tickers, "eps_diluted",
                             forms=("10-Q", "10-K"), keep=keep)
    if raw.empty:
        return raw
    raw = raw.rename(columns={"val": "eps"})
    # quarterly rows (Q1-Q3) reported on 10-Q
    q = raw[raw["fp"].isin(["Q1", "Q2", "Q3"])].copy()
    rows = [q]
    if derive_q4:
        fy = raw[(raw["fp"] == "FY") | (raw["form"] == "10-K")].copy()
        for (tk, year), gy in fy.groupby(["ticker", "fy"]):
            fy_eps = gy["eps"].iloc[-1]
            three = q[(q["ticker"] == tk) & (q["fy"] == year)]
            if len(three) == 3:
                q4 = fy_eps - three["eps"].sum()
                rows.append(pd.DataFrame([{
                    "ticker": tk, "fy": year, "fp": "Q4",
                    "end": gy["end"].iloc[-1], "eps": q4,
                    "filed": gy["filed"].iloc[-1], "form": "10-K",
                }]))
    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(["ticker", "end"]).reset_index(drop=True)


if __name__ == "__main__":
    import sys
    ua = sys.argv[1] if len(sys.argv) > 1 else "Example User example@example.com"
    ec = EdgarClient(ua)
    eps = quarterly_eps(ec, ["AAPL", "MSFT"])
    print(eps.tail(10).to_string(index=False))
