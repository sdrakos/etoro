"""Combined crypto + ETF daily panel for the diversity variation of the DMN build. Crypto trades
24/7, ETFs only on weekdays, so we align everything onto the ETF (business-day) calendar: crypto is
reindexed onto weekdays and forward-filled (a weekday's crypto price is its last 24/7 print). This
tests the 'thin universe' hypothesis from the crypto-only null — does an 18-asset, cross-asset-class
basket give the Sharpe-loss enough signal to beat the fixed rule? Annualise with PPY=252 (weekdays)."""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import crypto_data

ETF = ["SPY", "QQQ", "EEM", "EFA", "TLT", "IEF", "GLD", "DBC", "UUP", "XLE"]
DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combined_close.npz")


def align_combined(crypto, etf):
    """crypto: (T,N) 24/7 close; etf: (T,M) weekday close. Return a combined (T, N+M) panel on the
    ETF weekday calendar, from crypto's first date, with crypto reindexed+ffilled onto weekdays.
    Leading NaNs for not-yet-listed assets are preserved (build_features nan-cleans them to 0)."""
    cr = crypto.reindex(etf.index).ffill()
    combined = pd.concat([cr, etf], axis=1)
    combined = combined.loc[crypto.index[0]:]
    return combined.ffill().dropna(how="all")


def _fetch_etf(tickers=ETF, period="13y"):
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
    return pd.DataFrame(cols).sort_index()


def fetch_combined_daily(cache_path=DEFAULT_CACHE, refresh=False):
    """Return the aligned (T, 18) combined close DataFrame. Uses the npz cache unless refresh."""
    if not refresh and os.path.exists(cache_path):
        return crypto_data.load_cache(cache_path)
    crypto = crypto_data.fetch_crypto_daily()
    etf = _fetch_etf()
    combined = align_combined(crypto, etf)
    crypto_data.save_cache(cache_path, combined)
    return combined
