"""THE RULE — banded vol-targeted time-series momentum, as a single pure function.
The research harness AND the eToro engine both call `positions(...)`; never define it twice.

Canonical form (proven in paper4/paper5):
    pos = sign(close.pct_change(lookback)) * (target_vol / realized_vol.shift(1))
    pos = pos.clip(-clip, clip).fillna(0); pos = pos.ewm(span=smooth_span).mean()
The band and cost charging are applied downstream in eval.py — this returns DESIRED positions."""
from __future__ import annotations
import numpy as np
import pandas as pd

PPY = 252


def positions(close: pd.DataFrame, lookback: int = 120, vol_window: int = 30,
              target_vol: float = 0.15, clip: float = 2.0, smooth_span: int = 5,
              ppy: int = PPY) -> np.ndarray:
    """Desired position path. close: (T,N) price panel. Returns (T,N) float array.
    All estimates are causal: realized vol is `.shift(1)` so day t uses only past vol."""
    ret = close.pct_change()
    vol = ret.rolling(vol_window).std() * np.sqrt(ppy)
    raw = np.sign(close.pct_change(lookback)) * (target_vol / vol.shift(1))
    pos = raw.clip(-clip, clip).fillna(0.0)
    pos = pos.ewm(span=smooth_span, min_periods=1).mean()
    return pos.to_numpy()
