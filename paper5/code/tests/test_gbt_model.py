import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import gbt_model


def test_predict_to_position_zero_bounded_signflip():
    vol = np.array([0.5, 0.5])
    assert np.allclose(gbt_model.predict_to_position(np.array([0.0, 0.0]), vol, 1.0), 0.0)
    big = gbt_model.predict_to_position(np.array([100.0, -100.0]), vol, 1.0)
    assert np.all(np.abs(big) <= 2.0 + 1e-9)
    assert big[0] > 0 and big[1] < 0


def test_gbt_positions_shape_leakfree_bounded():
    rng = np.random.default_rng(0)
    N, T, F = 4, 220, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = (0.3 * X[:, :, 0] + rng.standard_normal((N, T)) * 0.5).astype("float32") * 0.01
    vol = np.full((N, T), 0.3, dtype="float32")
    folds = [(100, 150), (150, T)]
    POS, test_idx = gbt_model.gbt_positions(X, fwd, vol, folds, warm=20)
    assert POS.shape == (N, T)
    assert np.allclose(POS[:, :folds[0][0]], 0.0)
    assert np.isfinite(POS).all()
    assert np.all(np.abs(POS) <= 2.0 + 1e-6)
    assert test_idx.min() == folds[0][0]


def test_gbt_positions_deterministic():
    rng = np.random.default_rng(1)
    N, T, F = 4, 200, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    vol = np.full((N, T), 0.3, dtype="float32")
    folds = [(100, 150), (150, T)]
    a, _ = gbt_model.gbt_positions(X, fwd, vol, folds, warm=20)
    b, _ = gbt_model.gbt_positions(X, fwd, vol, folds, warm=20)
    assert np.allclose(a, b)
