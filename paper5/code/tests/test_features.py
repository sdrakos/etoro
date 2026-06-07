import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crypto_features


def _trending_close(T=400, N=3):
    # strictly increasing series per asset -> positive momentum at every horizon
    base = np.linspace(1.0, 5.0, T)
    vals = np.outer(base, np.arange(1, N + 1))
    idx = pd.date_range("2018-01-01", periods=T, freq="D")
    return pd.DataFrame(vals, index=idx, columns=[f"A{i}" for i in range(N)])


def test_shapes_and_finiteness():
    close = _trending_close()
    X, fwd, dates_ms = crypto_features.build(close)
    assert X.shape == (3, 400, 10)        # (N, T, F)
    assert fwd.shape == (3, 400)
    assert dates_ms.shape == (400,)
    assert np.isfinite(X).all()
    assert np.isfinite(fwd).all()
    # dates must be true epoch-MILLISECONDS (regression: a us/ns index must not yield seconds).
    # 2018-01-01 is 1514764800000 ms; allow the full 400-day span.
    assert 1_514_700_000_000 <= int(dates_ms[0]) <= 1_514_800_000_000


def test_uptrend_gives_positive_long_horizon_return_feature():
    close = _trending_close()
    X, _, _ = crypto_features.build(close)
    # feature index 2 is the 63-day return (LOOKBACKS=(1,21,63,126,252)); after warmup it must be > 0
    assert X[0, 200, 2] > 0
