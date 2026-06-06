import os, sys, tempfile
import numpy as np
import torch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "code")))
from dmn import DeepMomentumNetwork
from model_store import save, load


def test_save_load_roundtrip_preserves_output():
    net = DeepMomentumNetwork(n_features=10, hidden=8, dropout=0.0).eval()
    mu = np.zeros((1, 1, 10), dtype="float32"); sd = np.ones((1, 1, 10), dtype="float32")
    meta = {"tickers": ["SPY", "TLT"], "lookbacks": [1, 21, 63, 126, 252]}
    x = torch.randn(2, 30, 10)
    with torch.no_grad():
        before = net(x).numpy()
    with tempfile.TemporaryDirectory() as d:
        save(net, mu, sd, meta, name="t", root=d)
        net2, mu2, sd2, meta2 = load("t", root=d)
        with torch.no_grad():
            after = net2(x).numpy()
    assert np.allclose(before, after, atol=1e-6)
    assert np.array_equal(mu, mu2) and np.array_equal(sd, sd2)
    assert meta2["tickers"] == ["SPY", "TLT"]
