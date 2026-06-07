"""No-trade band: per-asset hysteresis applied to a (T,N) position path. Only switch to the
new target when |target - held| exceeds the band; otherwise keep the held position. This is the
decisive turnover lever (break-even ~ gross / turnover)."""
from __future__ import annotations
import numpy as np


def apply_band(pos, band):
    """pos: (T, N) desired positions over time. Returns held (T, N) actual positions."""
    pos = np.asarray(pos, float)
    T, N = pos.shape
    held = np.zeros_like(pos)
    cur = np.zeros(N)
    for t in range(T):
        upd = np.abs(pos[t] - cur) > band
        cur = np.where(upd, pos[t], cur)
        held[t] = cur
    return held
