from datetime import date
from unittest import mock
import pandas as pd
import pytest


def _fake_history_df():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"]).tz_localize("UTC")
    return pd.DataFrame(
        {"Open": [10.0, 11.0], "High": [12.0, 13.0], "Low": [9.0, 10.0],
         "Close": [11.0, 12.0], "Volume": [1000.0, 2000.0]},
        index=idx,
    )


def test_yahoo_fetch_bars_maps_rows():
    from trader.data.sources import yahoo
    with mock.patch.object(yahoo, "yf") as yf_mock:
        yf_mock.Ticker.return_value.history.return_value = _fake_history_df()
        rows = yahoo.fetch_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3))

    assert len(rows) == 2
    first = rows[0]
    assert first["ticker"] == "AAPL"
    assert first["open"] == 10.0 and first["close"] == 11.0
    assert first["vwap"] is None
    # 2024-01-02 00:00 UTC in ms
    assert first["timestamp"] == 1_704_153_600_000


def test_yahoo_passes_exclusive_end_plus_one_day():
    from trader.data.sources import yahoo
    with mock.patch.object(yahoo, "yf") as yf_mock:
        yf_mock.Ticker.return_value.history.return_value = _fake_history_df()
        yahoo.fetch_bars("AAPL", date(2024, 1, 2), date(2024, 1, 3))
        _, kwargs = yf_mock.Ticker.return_value.history.call_args
    assert kwargs["end"] == "2024-01-04"  # end + 1 day (yfinance end is exclusive)
    assert kwargs["start"] == "2024-01-02"
    assert kwargs["auto_adjust"] is True
