# paper6/code/data.py
"""5-asset sweet-spot loader for paper6 (the rule as a standalone strategy).
Reuses the proven paper5 deep-history Yahoo loader; never re-implements it."""
from __future__ import annotations
import os

import numpy as np
import pandas as pd

import _paths  # noqa: F401 — puts paper4/code + paper5/code on sys.path
import crypto_data  # noqa: E402  (paper5 deep-history loader)

PPY = 252  # mixed weekday/24-7 calendar; BTC trades weekends but ETFs gap — 252 is the convention used downstream

SWEET_SPOT = ("SPY", "TLT", "GLD", "BTC-USD", "UUP")

# real per-asset eToro spreads measured in paper5 (bps); used for net-cost eval
SPREADS_BPS = {"SPY": 2.0, "TLT": 3.0, "GLD": 3.0, "BTC-USD": 31.0, "UUP": 4.0}

CACHE = os.path.join(os.path.dirname(__file__), "paper6_close.npz")


def align_closes(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any row with a missing close in any column, so the panel is fully aligned."""
    return df.dropna(how="any")


def load_basket(tickers=SWEET_SPOT, period="20y") -> pd.DataFrame:
    """Aligned daily close panel for the basket (deep Yahoo history, npz-cached)."""
    df = crypto_data.fetch_crypto_daily(tickers=tuple(tickers), period=period, cache_path=CACHE)
    return align_closes(df)


def load_vix(period="20y") -> pd.Series:
    """^VIX daily close (for the Axis-2 VIX/regime gate). Not part of the traded basket."""
    vix = crypto_data.fetch_crypto_daily(tickers=("^VIX",), period=period,
                                         cache_path=os.path.join(os.path.dirname(__file__), "paper6_vix.npz"))
    return vix["^VIX"]
