import numpy as np
import torch

from features import build_features
from dmn import DeepMomentumNetwork, sharpe_loss, nested_walkforward


def _synth(T=400, N=4, seed=0):
    rng = np.random.default_rng(seed)
    return np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100


def test_features_shape_and_clean():
    X, fwd = build_features(_synth(T=300, N=5))
    assert X.shape == (5, 300, 10)         # N, T, F=10
    assert fwd.shape == (5, 300)
    assert not np.isnan(X).any() and not np.isinf(X).any()
    assert (np.abs(X) <= 10 + 1e-6).all()  # clipped


def test_dmn_outputs_positions_in_unit_range():
    net = DeepMomentumNetwork(n_features=10, hidden=8, dropout=0.0)
    x = torch.randn(4, 50, 10)
    with torch.no_grad():
        pos = net(x)
    assert pos.shape == (4, 50)
    assert pos.min() >= -1.0 and pos.max() <= 1.0


def test_sharpe_loss_finite():
    rng = np.random.default_rng(1)
    pos = torch.tensor(rng.normal(0, 0.5, (4, 200)), dtype=torch.float32)
    fwd = torch.tensor(rng.normal(0, 0.01, (4, 200)), dtype=torch.float32)
    loss = sharpe_loss(pos, fwd)
    assert torch.isfinite(loss)


def test_nested_walkforward_fills_test_span():
    X, fwd = build_features(_synth(T=600, N=4))
    # tiny grid + few epochs for speed; one fold
    POS, chosen, oos = nested_walkforward(
        X, fwd, [(450, 600)], warm=252, grid=[(4, 1e-2, 0.0)], epochs=20)
    assert POS.shape == (4, 600)
    assert len(chosen) == 1
    assert (oos == np.arange(450, 600)).all()
    assert np.abs(POS[:, 450:600]).max() <= 1.0      # positions in range on the test span
    assert np.allclose(POS[:, :450], 0.0)            # nothing written before the test span
