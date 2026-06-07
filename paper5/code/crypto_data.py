"""Crypto daily close panel for the paper5 DMN build. yfinance fetch with an npz cache
so reruns/tests don't re-hit the network. The cache stores values + epoch-ms dates + tickers."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

BASKET = ("BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "LTC-USD", "DOGE-USD")
DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto_close.npz")


def save_cache(path, close):
    # tickers stored as a NumPy unicode array (NOT object dtype) so load needs no allow_pickle.
    # Normalise to ns first so epoch-ms is correct regardless of the index resolution
    # (pandas 2.x may give us/ms/s-resolution datetimes from pd.to_datetime).
    dates_ms = close.index.as_unit("ns").view("int64") // 1_000_000
    np.savez(path, values=close.to_numpy(float),
             dates_ms=np.asarray(dates_ms, dtype="int64"),
             tickers=np.array([str(c) for c in close.columns]))


def load_cache(path):
    # allow_pickle stays False (default): all arrays are numeric or unicode, never pickled objects.
    z = np.load(path)
    # unit="ms" yields a datetime64[ms] index; cast to [us] so a round-trip matches the
    # default resolution pandas produces from pd.to_datetime(["YYYY-MM-DD", ...]).
    idx = pd.to_datetime(z["dates_ms"].astype("int64"), unit="ms").as_unit("us")
    return pd.DataFrame(z["values"], index=idx, columns=[str(t) for t in z["tickers"]])


def fetch_crypto_daily(tickers=BASKET, period="13y", cache_path=DEFAULT_CACHE, refresh=False):
    """Return a (T,N) daily close DataFrame. Uses the npz cache unless refresh=True."""
    if not refresh and os.path.exists(cache_path):
        return load_cache(cache_path)
    import yfinance as yf
    df = yf.download(list(tickers), period=period, interval="1d",
                     auto_adjust=True, progress=False, group_by="ticker")
    cols = {}
    for t in tickers:
        try:
            s = df[t]["Close"].dropna()
            if len(s) > 300:
                cols[t] = s
        except Exception:
            pass
    close = pd.DataFrame(cols).sort_index().ffill().dropna(how="all")
    save_cache(cache_path, close)
    return close
