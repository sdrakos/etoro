import datetime
import numpy as np
from etoro_backtest import parse_candles, build_closes, backtest_rules, _trailing_vol


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


def _trending_closes(T=700, N=4, seed=7):
    """Synthetic upward-drifting price panel with noise — enough warmup for a backtest."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.012, (T, N))
    return 100.0 * np.cumprod(1 + r, axis=0)


def test_trailing_vol_is_causal_and_annualized():
    rng = np.random.default_rng(1)
    net = rng.normal(0, 0.01, 400)
    vol = _trailing_vol(net, "rolling", window=63)
    assert np.isnan(vol[:63]).all()              # no estimate before the window fills
    # day t uses ONLY past returns -> equals the plain std of the trailing window
    assert np.isclose(vol[200], net[200 - 63:200].std() * np.sqrt(252))


def test_backtest_rolling_and_ewma_run_and_target_vol():
    close = _trending_closes()
    for m in ("static", "rolling", "ewma"):
        stats, a, eq = backtest_rules(close, capital=10000.0, target_vol=0.10, vol_method=m)
        assert eq[-1] > 0 and stats["n_days"] > 100
        assert np.isfinite(stats["ir"])
    # the causal methods land near (not exactly on) the 10% target — they are estimates
    _s, a_roll, _e = backtest_rules(close, target_vol=0.10, vol_method="rolling")
    assert 0.04 < a_roll.std() * np.sqrt(252) < 0.20
