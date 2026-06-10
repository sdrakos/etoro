# paper6/code/tests/test_data.py
import numpy as np
import pandas as pd
import data


def test_basket_constants():
    assert data.SWEET_SPOT == ("SPY", "TLT", "GLD", "BTC-USD", "UUP")
    # real per-asset spreads (bps): crypto wide, ETFs tight (paper5 measured)
    assert data.SPREADS_BPS["BTC-USD"] >= 25.0
    assert data.SPREADS_BPS["SPY"] <= 5.0


def test_align_closes_drops_partial_rows():
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    raw = pd.DataFrame(
        {"SPY": [1.0, 2.0, 3.0, 4.0], "BTC-USD": [np.nan, 2.0, 3.0, 4.0]}, index=idx
    )
    out = data.align_closes(raw)
    # first row has a NaN -> dropped; aligned frame has no NaNs
    assert not out.isna().any().any()
    assert len(out) == 3


def test_cache_path_distinct_per_ticker_set():
    # the underlying loader caches by path ignoring tickers, so different baskets
    # MUST map to different cache files; the same set (any order) maps to the same file.
    p_five = data._cache_path(("SPY", "TLT", "GLD", "BTC-USD", "UUP"))
    p_three = data._cache_path(("SPY", "TLT", "GLD"))
    assert p_five != p_three
    assert data._cache_path(("SPY", "TLT")) == data._cache_path(("TLT", "SPY"))  # order-independent
