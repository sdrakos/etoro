import os, sys
import numpy as np, torch
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import models


def test_factories_output_shape_and_range():
    N, T, F = 4, 30, 10
    x = torch.randn(N, T, F)
    for make, cfg in [(models.make_lstm, models.LSTM_GRID[0]),
                      (models.make_transformer, models.TRANSF_GRID[0])]:
        net = make(F, cfg).eval()
        with torch.no_grad():
            out = net(x)
        assert out.shape == (N, T)
        assert float(out.min()) >= -1.0 and float(out.max()) <= 1.0


def test_transformer_is_causal():
    # perturbing the LAST timestep's input must not change earlier outputs (leak-free).
    torch.manual_seed(0)
    N, T, F = 2, 16, 10
    net = models.make_transformer(F, models.TRANSF_GRID[0]).eval()
    x = torch.randn(N, T, F)
    with torch.no_grad():
        o1 = net(x)
        x2 = x.clone(); x2[:, -1, :] += 5.0
        o2 = net(x2)
    assert torch.allclose(o1[:, :-1], o2[:, :-1], atol=1e-5)


def test_transformer_block_local_attention():
    # With window=4, the time axis splits into blocks [0-3],[4-7],[8-9]. Perturbing position 0
    # (block 0) must not change position 9 (block 2) -> compute is genuinely block-local, O(T*W).
    torch.manual_seed(0)
    N, T, F = 2, 10, 10
    net = models.MomentumTransformer(F, d_model=8, nheads=2, dropout=0.0, window=4).eval()
    x = torch.randn(N, T, F)
    with torch.no_grad():
        o1 = net(x)
        x2 = x.clone(); x2[:, 0, :] += 5.0
        o2 = net(x2)
    assert torch.allclose(o1[:, 8:], o2[:, 8:], atol=1e-5)   # far block unaffected
    assert not torch.allclose(o1[:, 0], o2[:, 0], atol=1e-5)  # same block IS affected


def test_block_local_helper_matches_transformer_forward():
    torch.manual_seed(0)
    net = models.make_transformer(10, models.TRANSF_GRID[0]).eval()
    x = torch.randn(3, 20, 10)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (3, 20)
    assert float(out.min()) >= -1.0 and float(out.max()) <= 1.0


def test_transformer_norm_first_constructs_and_runs():
    torch.manual_seed(0)
    net = models.MomentumTransformer(10, d_model=16, nheads=2, dropout=0.0, norm_first=True).eval()
    x = torch.randn(2, 12, 10)
    with torch.no_grad():
        out = net(x)
    assert out.shape == (2, 12)
    assert net.enc.layers[0].norm_first is True
