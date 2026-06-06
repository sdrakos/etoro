import numpy as np
from ts_momentum import build_ts_weights


def test_ts_long_uptrend_short_downtrend():
    T = 400
    rng = np.random.default_rng(0)
    up = np.cumprod(1 + np.abs(rng.normal(0.001, 0.005, T))) * 100      # steady uptrend
    down = np.cumprod(1 - np.abs(rng.normal(0.001, 0.005, T))) * 100    # steady downtrend
    close = np.column_stack([up, down])
    W = build_ts_weights(close, rebal=21)
    assert W[300, 0] > 0 and W[300, 1] < 0      # long the riser, short the faller


def test_ts_shape_and_warmup():
    rng = np.random.default_rng(1)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (400, 5)), axis=0) * 100
    W = build_ts_weights(close)
    assert W.shape == (400, 5)
    assert np.allclose(W[:252], 0.0)                    # warmup zeroed
    assert np.nansum(np.abs(W[300])) <= 1.0 + 1e-9      # gross never exceeds 1


def test_ts_gate_reduces_gross():
    rng = np.random.default_rng(2)
    close = np.cumprod(1 + rng.normal(0.0005, 0.01, (400, 6)), axis=0) * 100
    sev = np.full((400, 6), 0.5)
    base = build_ts_weights(close, gate=False)
    gated = build_ts_weights(close, sev=sev, gate=True)
    assert np.nansum(np.abs(gated[300])) < np.nansum(np.abs(base[300]))
