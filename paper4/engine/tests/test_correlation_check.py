import numpy as np
from correlation_check import return_corr, effective_bets, avg_abs_offdiag


def test_effective_bets_uncorrelated_equals_n():
    rng = np.random.default_rng(0)
    corr = np.corrcoef(rng.normal(0, 1, (5000, 6)), rowvar=False)
    assert 5.3 < effective_bets(corr) <= 6.0        # ~6 independent bets for 6 uncorrelated assets


def test_effective_bets_identical_collapses_to_one():
    base = np.random.default_rng(1).normal(0, 1, 4000)
    x = np.column_stack([base, base, base, base])   # 4 identical columns
    corr = np.corrcoef(x + 1e-9 * np.random.default_rng(2).normal(0, 1, x.shape), rowvar=False)
    assert effective_bets(corr) < 1.5               # 4 names but ~1 real bet


def test_return_corr_shape_and_diag():
    close = 100 * np.cumprod(1 + np.random.default_rng(3).normal(0, 0.01, (300, 4)), axis=0)
    corr, rr = return_corr(close)
    assert corr.shape == (4, 4)
    assert np.allclose(np.diag(corr), 1.0)
    assert rr.shape == (299, 4)


def test_avg_abs_offdiag_range():
    rng = np.random.default_rng(4)
    corr = np.corrcoef(rng.normal(0, 1, (3000, 5)), rowvar=False)
    a = avg_abs_offdiag(corr)
    assert 0.0 <= a < 0.1                            # uncorrelated -> small average |corr|
