import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lstm_sizing as ls


def test_zero_target_vol_zero_position():
    POS = np.full((3, 10), 0.5); vol = np.full((3, 10), 0.2)
    assert np.allclose(ls.size_positions(POS, vol, target_vol=0.0), 0.0)


def test_inverse_vol_halves_when_vol_doubles():
    POS = np.full((2, 20), 0.5)
    a = ls.size_positions(POS, np.full((2, 20), 0.2), target_vol=0.15, clip=10.0, ewm_span=1)
    b = ls.size_positions(POS, np.full((2, 20), 0.4), target_vol=0.15, clip=10.0, ewm_span=1)
    assert np.allclose(b, a / 2.0, atol=1e-9)


def test_clip_caps_at_two_and_shape():
    POS = np.ones((2, 5)); vol = np.full((2, 5), 0.01)
    out = ls.size_positions(POS, vol, target_vol=0.15, clip=2.0, ewm_span=1)
    assert out.shape == (2, 5)
    assert np.all(np.abs(out) <= 2.0 + 1e-9) and np.isfinite(out).all()


def test_smoothing_softens_a_step():
    POS = np.array([[0.0, 0, 0, 1.0, 1, 1, 1, 1]]); vol = np.full((1, 8), 1.0)
    out = ls.size_positions(POS, vol, target_vol=1.0, clip=10.0, ewm_span=5)
    assert 0.0 < out[0, 3] < 1.0
