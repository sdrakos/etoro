import numpy as np
from metrics import ann_ir, max_drawdown, newey_west_t, deflated_sharpe, durability_by_year

def test_ann_ir_positive_drift():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0005, 0.01, 2520)
    assert ann_ir(r) > 0.3

def test_max_drawdown_known():
    r = np.array([0.1, -0.5, 0.0])
    dd = max_drawdown(r)
    assert dd < -0.45 and dd > -0.55

def test_newey_west_t_zero_mean_small():
    rng = np.random.default_rng(4)              # stable seed: zero-mean -> |t| ~ 0.3
    r = rng.normal(0.0, 0.01, 2000)
    assert abs(newey_west_t(r, lag=21)) < 2.5

def test_deflated_sharpe_penalizes_trials():
    rng = np.random.default_rng(3)
    r = rng.normal(0.0008, 0.01, 2520)
    dsr_1 = deflated_sharpe(r, n_trials=1)
    dsr_50 = deflated_sharpe(r, n_trials=50)
    assert dsr_50 <= dsr_1

def test_durability_by_year_keys():
    dates_ms = (np.arange(504) * 86400000 + 946684800000)  # ~2 years of days from 2000
    r = np.full(504, 0.001)
    d = durability_by_year(r, dates_ms)
    assert len(d) >= 1
    assert all(isinstance(k, int) for k in d)
