import numpy as np
from sideways_check import efficiency_ratio, regime_masks


def test_efficiency_ratio_trend_high_chop_low():
    T = 200
    trend = np.cumsum(np.full(T, 0.5)) + 100          # straight line up -> ER ~ 1
    chop = 100 + np.tile([0.0, 1.0], T // 2)          # oscillates in place -> ER ~ 0
    close = np.column_stack([trend, chop])
    er = efficiency_ratio(close, n=63)
    assert er[150, 0] > 0.9                            # clean trend
    assert er[150, 1] < 0.1                            # pure chop


def test_efficiency_ratio_warmup_nan():
    close = 100 + np.cumsum(np.random.default_rng(0).normal(0, 1, (120, 2)), axis=0)
    er = efficiency_ratio(close, n=63)
    assert np.isnan(er[:63]).all()                    # no estimate before the window fills


def test_regime_masks_partition_and_disjoint():
    rng = np.random.default_rng(1)
    er = rng.uniform(0, 1, (400, 3))
    masks, (lo, hi) = regime_masks(er, warm=252)
    assert lo < hi
    # the three regimes are disjoint and cover all valid post-warmup cells
    total = masks["sideways"].sum() + masks["mixed"].sum() + masks["trending"].sum()
    assert total == (400 - 252) * 3
    assert not (masks["sideways"] & masks["trending"]).any()
