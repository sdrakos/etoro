import numpy as np
from signals import zscore_xs, xs_weights, build_weights, momentum_matrix

def test_xs_weights_dollar_neutral():
    score = np.array([3.0, 1.0, -1.0, -3.0, np.nan])
    w = xs_weights(score, k=1)
    assert np.isclose(np.nansum(w), 0.0)
    assert np.isclose(np.nansum(np.abs(w)), 1.0)
    assert w[0] > 0 and w[3] < 0

def test_xs_weights_too_few_valid_returns_zero():
    w = xs_weights(np.array([1.0, np.nan, np.nan]), k=2)
    assert np.allclose(w, 0.0)

def test_momentum_matrix_shape_and_warmup():
    close = np.cumprod(1 + np.zeros((300, 5)) + 0.001, axis=0) * 100
    M = momentum_matrix(close, lookback=252, skip=21)
    assert M.shape == (300, 5)
    assert np.isnan(M[100]).all()
    assert np.isfinite(M[260]).all()

def test_build_weights_variants_run():
    T, N = 300, 6
    rng = np.random.default_rng(0)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100
    vel = rng.normal(0, 1e-3, (T, N))
    sig = rng.normal(0, 1, (T, N))
    sev = np.abs(rng.normal(0, 0.1, (T, N))).clip(0, 1)
    for variant in ("tsmom", "cpd_momentum", "belief_gated"):
        W = build_weights(variant, close, vel, sig, sev, k=2, warmup=252)
        assert W.shape == (T, N)
        assert np.allclose(W[:252], 0.0)
        row = W[260]
        assert abs(np.nansum(row)) < 1e-9
        assert np.nansum(np.abs(row)) <= 1.0 + 1e-9

def test_belief_gated_trades_only_significant_names():
    # belief_gated must EXCLUDE statistically-insignificant trends (composition changes IR,
    # unlike a magnitude scale which xs_weights normalizes away).
    T, N = 300, 20
    rng = np.random.default_rng(1)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100
    vel = rng.normal(0, 1e-3, (T, N))
    sev = np.zeros((T, N))
    sig = np.zeros((T, N)); sig[:, :10] = 5.0; sig[:, 10:] = 0.1   # first 10 significant
    W = build_weights("belief_gated", close, vel, sig, sev, k=3, warmup=252, sig_thresh=1.0)
    row = W[260]
    assert np.allclose(row[10:], 0.0)               # insignificant names never traded
    assert np.nansum(np.abs(row)) > 0               # significant names do trade
