"""Save/load the frozen Deep Momentum Network: weights (.pt) + frozen feature scaler (mu/sd) +
meta (universe, lookbacks). Loading reconstructs the net from meta and reuses it for inference."""
from __future__ import annotations
import os, sys, json
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code")))
from dmn import DeepMomentumNetwork   # noqa: E402

DEFAULT_ROOT = os.path.expanduser(os.path.join("~", ".etoro", "models"))


def save(net, mu, sd, meta, name, root=DEFAULT_ROOT):
    d = os.path.join(root, name); os.makedirs(d, exist_ok=True)
    torch.save(net.state_dict(), os.path.join(d, "model.pt"))
    np.savez(os.path.join(d, "scaler.npz"), mu=np.asarray(mu), sd=np.asarray(sd))
    full = dict(meta); full["hidden"] = net.lstm.hidden_size
    full["n_features"] = net.lstm.input_size
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(full, f)


def load(name, root=DEFAULT_ROOT):
    d = os.path.join(root, name)
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    net = DeepMomentumNetwork(n_features=meta["n_features"], hidden=meta["hidden"], dropout=0.0)
    net.load_state_dict(torch.load(os.path.join(d, "model.pt"), weights_only=True))  # tensors only
    net.eval()
    z = np.load(os.path.join(d, "scaler.npz"))
    return net, z["mu"], z["sd"], meta
