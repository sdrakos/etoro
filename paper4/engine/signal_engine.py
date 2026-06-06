"""Fresh prices -> target weights {ticker: signed weight}. Rules variant is deterministic and
needs no model; ML variant loads a frozen DMN + scaler and runs inference on the latest bar.
Also provides train_full: train ONE DMN on all history (for the admin `retrain` command)."""
from __future__ import annotations
import os, sys
import numpy as np
import torch

_CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if _CODE not in sys.path:
    sys.path.insert(0, _CODE)
from features import build_features              # noqa: E402
from ts_momentum import build_ts_weights         # noqa: E402
from dmn import DeepMomentumNetwork, sharpe_loss  # noqa: E402
from model_store import save as _save, load as _load  # noqa: E402


def target_weights(strategy, fetch_close, model_name="prod", model_root=None):
    close, tickers = fetch_close()
    if strategy == "rules":
        W = build_ts_weights(close)
        row = W[-1]
        return {tk: float(row[j]) for j, tk in enumerate(tickers)}
    elif strategy == "ml":
        X, _ = build_features(close)
        kw = {} if model_root is None else {"root": model_root}
        net, mu, sd, _ = _load(model_name, **kw)
        xt = (torch.tensor(X, dtype=torch.float32) - torch.tensor(mu)) / torch.tensor(sd)
        with torch.no_grad():
            pos = net(xt).numpy()
        return {tk: float(pos[j, -1]) for j, tk in enumerate(tickers)}
    raise ValueError(f"unknown strategy {strategy!r}")


def train_full(close, tickers, name="prod", root=None, epochs=300, val_frac=0.15):
    """Train ONE DMN on all history with a validation tail for early stopping; freeze + save."""
    X, fwd = build_features(close)
    torch.manual_seed(0)
    T = X.shape[1]; vlo = int(T * (1 - val_frac))
    Xt = torch.tensor(X[:, :T], dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True); sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (torch.tensor(X[:, :vlo], dtype=torch.float32) - mu) / sd
    ftr = torch.tensor(fwd[:, :vlo], dtype=torch.float32)
    Xv = (torch.tensor(X[:, vlo:], dtype=torch.float32) - mu) / sd
    fv = torch.tensor(fwd[:, vlo:], dtype=torch.float32)
    net = DeepMomentumNetwork(X.shape[2], hidden=16, dropout=0.0)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-3)
    best, best_state = float("inf"), None
    for e in range(epochs):
        net.train(); opt.zero_grad(); sharpe_loss(net(Xtr), ftr).backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        if e % 10 == 0:
            net.eval()
            with torch.no_grad():
                v = float(sharpe_loss(net(Xv), fv))
            if v < best:
                best, best_state = v, {k: val.clone() for k, val in net.state_dict().items()}
    net.load_state_dict(best_state); net.eval()
    meta = {"tickers": list(tickers), "lookbacks": [1, 21, 63, 126, 252]}
    kw = {} if root is None else {"root": root}
    _save(net, mu.numpy(), sd.numpy(), meta, name=name, **kw)
    return name
