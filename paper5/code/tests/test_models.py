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
