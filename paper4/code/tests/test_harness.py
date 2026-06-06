import numpy as np
from harness import run_variant, per_asset_states

def _rw_universe(T=600, N=8, seed=0):
    rng = np.random.default_rng(seed)
    return np.cumprod(1 + rng.normal(0.0, 0.01, (T, N)), axis=0) * 100

def test_clean_null_no_significant_edge():
    # random-walk universe -> no real signal: IR small AND not statistically significant.
    rng = np.random.default_rng(0)
    close = np.cumprod(1 + rng.normal(0.0, 0.01, (2000, 30)), axis=0) * 100
    res = run_variant("tsmom", close, k=5, warmup=252,
                      spread_bps=0.0, short_fin_bps_annual=0.0)
    assert abs(res["ir"]) < 0.5
    assert abs(res["nw_t"]) < 2.0

def test_states_shapes():
    close = _rw_universe(T=300, N=4)
    vel, sig, sev = per_asset_states(close)
    assert vel.shape == sig.shape == sev.shape == (300, 4)

def test_returns_length_matches():
    close = _rw_universe(T=400, N=5)
    res = run_variant("cpd_momentum", close, k=1, warmup=252)
    assert len(res["net"]) == 400
    assert np.allclose(res["net"][:252], 0.0)
