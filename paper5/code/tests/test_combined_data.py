import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import combined_data


def test_align_uses_weekday_calendar_and_ffills_crypto():
    cr_idx = pd.date_range("2020-01-01", periods=10, freq="D")   # incl weekends
    etf_idx = pd.bdate_range("2020-01-01", periods=6)            # weekdays only
    crypto = pd.DataFrame({"BTC-USD": np.arange(10.) + 1}, index=cr_idx)
    etf = pd.DataFrame({"SPY": np.arange(6.) + 100}, index=etf_idx)
    comb = combined_data.align_combined(crypto, etf)
    assert list(comb.index) == list(etf_idx)               # weekday calendar
    assert "BTC-USD" in comb.columns and "SPY" in comb.columns
    assert not comb.isna().any().any()                     # no gaps in the overlap


def test_align_preserves_leading_nan_for_late_listed_asset():
    etf_idx = pd.bdate_range("2020-01-01", periods=6)
    cr_idx = pd.date_range("2020-01-01", periods=10, freq="D")
    # SOL listed only from the 3rd weekday onward -> earlier rows must stay NaN (not back-filled)
    sol = pd.Series([np.nan, np.nan, 5.0, 6.0, 7.0, 8.0], index=etf_idx)
    crypto = pd.DataFrame({"BTC-USD": np.arange(10.) + 1}, index=cr_idx)
    etf = pd.DataFrame({"SPY": np.arange(6.) + 100, "SOL-USD": sol.values}, index=etf_idx)
    comb = combined_data.align_combined(crypto, etf)
    assert np.isnan(comb["SOL-USD"].iloc[0])               # leading NaN preserved (no look-ahead)
    assert comb["SOL-USD"].iloc[2] == 5.0
