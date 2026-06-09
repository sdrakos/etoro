import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import etoro_gbt_backtest as eb


def test_net_per_asset_zero_turnover_zero_cost():
    T, N = 5, 3
    W = np.zeros((T, N))
    fwd = np.zeros((T, N))
    net = eb.net_per_asset(W, fwd, np.array([10.0, 10.0, 10.0]))
    assert net.shape == (T,)
    assert np.allclose(net, 0.0)


def test_net_per_asset_higher_spread_lowers_net():
    T, N = 4, 2
    W = np.array([[1.0, 0.5], [-1.0, 0.5], [1.0, 0.5], [-1.0, 0.5]])
    fwd = np.full((T, N), 0.01)
    lo = eb.net_per_asset(W, fwd, np.array([1.0, 1.0]))
    hi = eb.net_per_asset(W, fwd, np.array([200.0, 1.0]))
    assert hi.sum() < lo.sum()


def test_panel_to_xy_shapes():
    T, N = 400, 3
    base = np.linspace(1.0, 3.0, T)
    close = np.outer(base, np.arange(1, N + 1))
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2021-01-01", periods=T)]
    X, fwd, dates_ms, vol, ppy, df = eb.panel_to_xy(close, dates)
    assert X.shape == (N, T, 10)
    assert fwd.shape == (N, T)
    assert vol.shape == (N, T)
    assert np.isfinite(X).all() and np.isfinite(vol).all()
    assert ppy > 0
