import numpy as np
from sizing import (ledoit_wolf_cov, inverse_vol_weights, min_variance_weights,
                    hrp_weights, kelly_leverage)


def _cov(seed=0, n=5, w=400):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, (w, n))
    r[:, 0] *= 3.0                       # asset 0 is much more volatile
    return r


def test_inverse_vol_higher_weight_for_calmer():
    r = _cov(); cov = np.cov(r, rowvar=False)
    w = inverse_vol_weights(cov)
    assert np.isclose(w.sum(), 1.0)
    assert w[0] == w.min()               # most volatile asset gets least weight


def test_hrp_weights_valid_and_sum_one():
    cov = np.cov(_cov(), rowvar=False)
    w = hrp_weights(cov)
    assert w.shape == (5,)
    assert np.isclose(w.sum(), 1.0)
    assert (w > 0).all()                 # long-only risk budgets
    assert w[0] < w.mean()               # volatile asset down-weighted


def test_hrp_single_asset():
    assert np.allclose(hrp_weights(np.array([[0.04]])), [1.0])


def test_min_variance_reduces_variance_vs_equal():
    cov = np.cov(_cov(), rowvar=False); n = cov.shape[0]
    w_mv = min_variance_weights(cov); w_eq = np.ones(n) / n
    assert np.isclose(w_mv.sum(), 1.0)
    assert (w_mv @ cov @ w_mv) <= (w_eq @ cov @ w_eq) + 1e-12


def test_kelly_leverage_sign_and_fraction():
    rng = np.random.default_rng(1)
    good = rng.normal(0.0005, 0.01, 2000)         # positive drift
    assert kelly_leverage(good, fraction=1.0) > 0
    assert kelly_leverage(good, fraction=0.5) < kelly_leverage(good, fraction=1.0)
    bad = rng.normal(-0.0005, 0.01, 2000)         # negative drift -> no leverage
    assert kelly_leverage(bad) == 0.0
    assert kelly_leverage(good, fraction=10.0, cap=2.0) == 2.0   # capped


def test_ledoit_wolf_cov_shape_psd():
    cov = ledoit_wolf_cov(_cov())
    assert cov.shape == (5, 5)
    assert np.all(np.linalg.eigvalsh(cov) > -1e-10)   # PSD
