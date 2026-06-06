import datetime
import numpy as np
from etoro_backtest import parse_candles, build_closes


def _raw(n=400, base=100.0):
    """A fake eToro candle response: n daily candles, newest-first (desc), with fromDate+close."""
    d0 = datetime.date(2020, 1, 1)
    cs = [{"fromDate": (d0 + datetime.timedelta(days=k)).isoformat() + "T00:00:00Z",
           "close": base + k * 0.1} for k in range(n)]
    return {"candles": [{"candles": list(reversed(cs))}]}   # desc


def test_parse_candles_ascending():
    out = parse_candles(_raw(3))
    assert [d for d, _ in out] == ["2020-01-01", "2020-01-02", "2020-01-03"]
    assert out[0][1] < out[-1][1]                # ascending close


def test_parse_candles_empty_safe():
    assert parse_candles({}) == []
    assert parse_candles({"candles": []}) == []


def test_build_closes_common_grid_filters_short_series():
    def fetch(iid):
        return _raw(400 if iid != 9 else 100)    # id 9 has too few days (<300) -> dropped
    close, dates, ids = build_closes(fetch, [1, 2, 9])
    assert ids == [1, 2]                          # short series filtered out
    assert close.shape == (400, 2)
    assert not np.isnan(close).any()             # aligned, fully populated
