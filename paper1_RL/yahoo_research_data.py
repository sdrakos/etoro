# paper1_RL/yahoo_research_data.py
"""Offline-reproducible Yahoo data layer για το signal-engine experiment.
Live fetch -> cache σε npz (μια φορα)· οι transforms ειναι pure & tested."""
from __future__ import annotations
import numpy as np

def announcement_index(all_ts, day_ms: int):
    """Index του πλησιεστερου trading day <= day_ms. None αν το event ειναι
    ΕΚΤΟΣ του [first, last] window (π.χ. μελλοντικα earnings) — αλλιως μελλοντικες
    ανακοινωσεις θα κλειδωναν λαθος στον τελευταιο index. all_ts: sorted ints."""
    if len(all_ts) == 0 or day_ms < all_ts[0] or day_ms > all_ts[-1]:
        return None
    return int(np.searchsorted(all_ts, day_ms, side="right") - 1)

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

import os, sys, warnings, datetime as dt

def _fetch_all() -> dict:
    """LIVE Yahoo pull (μη-ντετερμινιστικο· δεν μπαινει σε unit test).
    Reuse του trader bar-fetcher για OHLCV."""
    import yfinance as yf
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from trader.data.sources.yahoo import fetch_bars
    from datetime import date
    from . import universe as U

    start = date.fromisoformat(U.START); end = date.fromisoformat(U.END)
    # 1) bars -> close/vol matrices σε κοινο date index
    per_ticker = {}
    for tk in U.TICKERS:
        try:
            rows = fetch_bars(tk, start, end, "day")
            per_ticker[tk] = {r["timestamp"]: (r["close"], r["volume"]) for r in rows}
        except Exception as e:
            warnings.warn(f"bars {tk}: {e}")
    all_ts = sorted(set().union(*[set(d) for d in per_ticker.values()]))
    tickers = [t for t in U.TICKERS if t in per_ticker]
    T, N = len(all_ts), len(tickers)
    close = np.full((T, N), np.nan); vol = np.full((T, N), np.nan)
    ts_idx = {ts: i for i, ts in enumerate(all_ts)}
    for j, tk in enumerate(tickers):
        for ts, (c, v) in per_ticker[tk].items():
            close[ts_idx[ts], j] = c; vol[ts_idx[ts], j] = v
    # 2) earnings announcements -> date_index στο all_ts grid
    earnings = {j: [] for j in range(N)}
    for j, tk in enumerate(tickers):
        try:
            ed = yf.Ticker(tk).get_earnings_dates(limit=60)
            if ed is None: continue
            for ts_pd, row in ed.iterrows():
                surp = row.get("Surprise(%)")
                if surp is None or np.isnan(surp): continue
                day_ms = int(dt.datetime(ts_pd.year, ts_pd.month, ts_pd.day,
                             tzinfo=dt.timezone.utc).timestamp() * 1000)
                idx = announcement_index(all_ts, day_ms)   # None αν εκτος window (π.χ. future)
                if idx is not None: earnings[j].append((idx, float(surp)))
        except Exception as e:
            warnings.warn(f"earnings {tk}: {e}")
    # 3) sector map
    sector = {}
    for tk in tickers:
        try: sector[tk] = yf.Ticker(tk).info.get("sector", "Unknown")
        except Exception: sector[tk] = "Unknown"
    # 4) VIX aligned στο all_ts
    vix = np.full(T, np.nan)
    try:
        vrows = fetch_bars("^VIX", start, end, "day")
        vmap = {r["timestamp"]: r["close"] for r in vrows}
        for ts, i in ts_idx.items():
            if ts in vmap: vix[i] = vmap[ts]
    except Exception as e:
        warnings.warn(f"vix: {e}")
    return dict(close=close, vol=vol, dates=np.array(all_ts), tickers=tickers,
                earnings=earnings, sector=sector, vix=vix)

def load_universe(cache_path: str = "universe_cache.npz") -> dict:
    """Cache-aside. ΧΩΡΙΣ pickle (security): αριθμητικα arrays -> npz·
    τα dicts/lists (earnings/sector/tickers) -> JSON sidecar. Self-generated
    local cache, αλλα αποφευγουμε allow_pickle εντελως."""
    import json
    side = cache_path + ".json"
    if os.path.exists(cache_path) and os.path.exists(side):
        z = np.load(cache_path)                          # no allow_pickle
        with open(side, encoding="utf-8") as f:
            meta = json.load(f)
        earnings = {int(k): [tuple(ev) for ev in v] for k, v in meta["earnings"].items()}
        return dict(close=z["close"], vol=z["vol"], dates=z["dates"], vix=z["vix"],
                    tickers=meta["tickers"], sector=meta["sector"], earnings=earnings)
    d = _fetch_all()
    np.savez(cache_path, close=d["close"], vol=d["vol"], dates=d["dates"], vix=d["vix"])
    with open(side, "w", encoding="utf-8") as f:
        json.dump(dict(tickers=list(d["tickers"]), sector=d["sector"],
                       earnings={str(k): v for k, v in d["earnings"].items()}), f)
    return d
