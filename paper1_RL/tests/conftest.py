import numpy as np
import pytest

T, N = 600, 60  # μέρες, μετοχές

@pytest.fixture
def rng():
    return np.random.default_rng(2025)

@pytest.fixture
def planted(rng):
    """Universe όπου ενα κρυφο score προβλεπει την επομενη ημερησια αποδοση.
    Επιστρεφει (close, score, fwd) με γνωστο θετικο IC."""
    score = rng.standard_normal((T, N))                  # ο "predictor"
    noise = rng.standard_normal((T, N)) * 0.02
    fwd = 0.01 * score + noise                           # next-day return, IC>0 by construction
    ret = np.zeros((T, N)); ret[1:] = fwd[:-1]           # close-to-close = lagged fwd
    close = 100.0 * np.cumprod(1 + ret, axis=0)
    return dict(close=close, score=score, fwd=fwd)

@pytest.fixture
def noise_only(rng):
    """Universe χωρις σχεση score↔return (IC≈0)."""
    score = rng.standard_normal((T, N))
    ret = rng.standard_normal((T, N)) * 0.02
    close = 100.0 * np.cumprod(1 + ret, axis=0)
    return dict(close=close, score=score)
