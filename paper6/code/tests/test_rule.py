import numpy as np
import pandas as pd
import rule


def _ramp_panel(n=400):
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    up = pd.Series(np.linspace(100, 200, n), index=idx)      # steady uptrend
    down = pd.Series(np.linspace(200, 100, n), index=idx)    # steady downtrend
    return pd.DataFrame({"UP": up, "DOWN": down})


def test_sign_follows_trend():
    df = _ramp_panel()
    pos = rule.positions(df, lookback=120, vol_window=30, target_vol=0.15)
    # after warmup, long the uptrend, short the downtrend
    last = pos[-1]
    cols = list(df.columns)
    assert last[cols.index("UP")] > 0
    assert last[cols.index("DOWN")] < 0


def test_vol_target_scales_inverse_to_vol():
    # higher realized vol -> smaller absolute position for the same trend sign
    idx = pd.date_range("2018-01-01", periods=400, freq="D")
    calm = np.cumprod(1 + np.full(400, 0.001))               # smooth uptrend, low vol
    wild = np.cumprod(1 + 0.001 + 0.02 * np.sin(np.arange(400)))  # same drift, high vol
    df = pd.DataFrame({"CALM": calm * 100, "WILD": wild * 100}, index=idx)
    pos = rule.positions(df, lookback=120, vol_window=30, target_vol=0.15)
    last = np.abs(pos[-1])
    cols = list(df.columns)
    assert last[cols.index("CALM")] > last[cols.index("WILD")]


def test_output_shape_and_clip():
    df = _ramp_panel()
    pos = rule.positions(df, lookback=120, vol_window=30, target_vol=0.15, clip=2.0)
    assert pos.shape == (len(df), df.shape[1])      # (T, N)
    assert np.all(np.abs(pos) <= 2.0 + 1e-9)
    assert np.all(np.isfinite(pos))                 # warmup NaNs filled with 0
