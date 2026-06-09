"""Volatility-target sizing for the LSTM signal (serving-time, no retraining). The LSTM emits a
tanh position in [-1,1] (direction + conviction); we re-scale it by inverse vol like the fixed rule:
position = clip(LSTM * target_vol/vol, +/-clip), then per-asset EWM. The no-trade band is applied
downstream by evaluate(). target_vol is the profit/risk dial."""
from __future__ import annotations
import numpy as np
import pandas as pd


def size_positions(POS, vol, target_vol=0.15, clip=2.0, ewm_span=5):
    """POS (N,T) raw LSTM tanh positions; vol (N,T) causal annualized realized vol.
    Returns vol-targeted positions (N,T)."""
    sized = np.clip(np.asarray(POS, float) * (target_vol / np.maximum(np.asarray(vol, float), 1e-6)),
                    -clip, clip)
    return pd.DataFrame(sized.T).ewm(span=ewm_span, min_periods=1).mean().to_numpy().T
