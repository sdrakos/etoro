import numpy as np
from kalman_llt import kalman_llt   # run pytest from the package dir, or use full path import

def test_recovers_linear_trend():
    t = np.arange(400)
    b = 0.01
    rng = np.random.default_rng(0)
    y = 5.0 + b * t + rng.normal(0, 1e-3, 400)
    out = kalman_llt(y, q_level=1e-5, q_vel=1e-7, r_obs=1e-6)
    assert abs(np.mean(out["velocity"][-50:]) - b) < 2e-3

def test_innovation_spikes_at_level_break():
    rng = np.random.default_rng(1)
    y = np.concatenate([np.zeros(150), np.full(150, 0.5)]) + rng.normal(0, 1e-3, 300)
    out = kalman_llt(y, q_level=1e-5, q_vel=1e-7, r_obs=1e-6)
    si = np.abs(out["std_innov"])
    assert si[150] > 5.0
    assert si[150] >= si[50:140].max()

def test_output_keys_and_length():
    out = kalman_llt(np.linspace(0, 1, 50))
    for k in ("level","velocity","vel_var","innovation","innov_var","trend_sig","std_innov"):
        assert out[k].shape == (50,)
