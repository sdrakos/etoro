# paper1_RL/yahoo_research_data.py
"""Offline-reproducible Yahoo data layer για το signal-engine experiment.
Live fetch -> cache σε npz (μια φορα)· οι transforms ειναι pure & tested."""
from __future__ import annotations
import numpy as np

def surprise_matrix(dates, announcements: dict[int, list[tuple[int, float]]],
                    n: int, window: int = 60) -> np.ndarray:
    """(T,N) matrix· για καθε (ticker j) και drift window [ann+1, ann+window]
    γραφει το Surprise%· entry T+1 (no look-ahead). Default nan.

    announcements[j] = list of (date_index, surprise_pct).
    """
    T = len(dates)
    M = np.full((T, n), np.nan)
    for j, evs in announcements.items():
        for (di, surp) in evs:
            lo, hi = di + 1, min(di + window, T - 1)     # [+1, +window], inclusive
            if lo <= hi:
                M[lo:hi + 1, j] = surp
    return M
