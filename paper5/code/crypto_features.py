"""Turn a (T,N) close DataFrame into the paper4 10-feature tensor X (N,T,10),
next-day target fwd (N,T), and aligned epoch-ms dates (T,)."""
from __future__ import annotations
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import features  # paper4


def build(close_df):
    close = close_df.to_numpy(float)               # (T, N)
    X, fwd = features.build_features(close)         # X (N,T,10), fwd (N,T)
    # Resolution-agnostic epoch-ms: astype("datetime64[ms]") normalises any index resolution
    # (ns/us from load_cache) before viewing as int64, so this is always milliseconds.
    dates_ms = close_df.index.astype("datetime64[ms]").view("int64")
    return X, fwd, np.asarray(dates_ms, dtype="int64")
