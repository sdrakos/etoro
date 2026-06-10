import numpy as np
import pandas as pd
import eval as ev


def test_forward_returns_are_causal():
    # forward return at row t must equal (P[t+1]/P[t] - 1); last row is NaN
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    close = pd.DataFrame({"A": [100.0, 110.0, 99.0, 99.0]}, index=idx)
    fwd = ev.forward_returns(close)
    assert np.isclose(fwd[0, 0], 0.10)            # 100 -> 110
    assert np.isclose(fwd[1, 0], -0.10)           # 110 -> 99
    assert np.isnan(fwd[-1, 0])                    # no future for the last row


def test_evaluate_flat_book_is_zero_return():
    # zero positions -> zero net return -> IR is 0 (or nan), never a crash
    T, N = 50, 2
    pos = np.zeros((T, N))
    fwd = np.full((T, N), 0.01)
    res = ev.evaluate(pos, fwd, test_rows=np.arange(10, T), spreads_bps=[2.0, 2.0], band=0.1)
    assert abs(res["net_ir"]) < 1e-9 or np.isnan(res["net_ir"])
    assert res["n"] == T - 10


def test_costs_reduce_return():
    # a positive trend book nets less after spread than a zero-spread book
    T, N = 60, 1
    pos = np.ones((T, N))
    fwd = np.full((T, N), 0.005)
    gross = ev.evaluate(pos, fwd, np.arange(5, T), spreads_bps=[0.0], band=0.0)["net_ir"]
    net = ev.evaluate(pos, fwd, np.arange(5, T), spreads_bps=[50.0], band=0.0)["net_ir"]
    assert net <= gross
