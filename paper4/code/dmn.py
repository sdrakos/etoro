"""Deep Momentum Network (LSTM) trained with a Sharpe-ratio loss, plus an HONEST
nested walk-forward that selects hyperparameters on a validation split it never lets touch
the out-of-sample test (and early-stops on the same split).

One shared LSTM is applied per asset: it reads only that asset's own feature sequence and
emits a position in [-1,1] (tanh). The training objective is the Sharpe of the WHOLE
18-asset portfolio net of turnover cost, so diversification is baked into the loss.
"""
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn

# (hidden, weight_decay, dropout) grid searched per fold on validation only.
GRID = [(16, 1e-3, 0.0), (16, 1e-2, 0.3), (8, 1e-2, 0.3), (8, 1e-3, 0.4), (4, 1e-2, 0.3)]


class DeepMomentumNetwork(nn.Module):
    def __init__(self, n_features, hidden=16, dropout=0.0):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):                       # x (N,T,F) -> positions (N,T) in [-1,1]
        out, _ = self.lstm(x)
        return torch.tanh(self.head(self.drop(out))).squeeze(-1)


def sharpe_loss(pos, fwd, cost=5e-4):
    """-Sharpe of the equal-capital portfolio of `pos` against next-day returns `fwd`,
    charging `cost` on daily turnover. pos, fwd: (N, T) tensors."""
    port = (pos * fwd).mean(0)
    turn = torch.abs(pos[:, 1:] - pos[:, :-1]).mean(0)
    port = port - torch.cat([torch.zeros(1), cost * turn])
    return -port.mean() / (port.std() + 1e-6)


def _train_fold(X, fwd, lo, hi, hidden, wd, dropout, epochs=400, val_frac=0.2):
    """Train on [lo, hi) with the last `val_frac` as validation for early stopping.
    Returns (net, mu, sd, best_val_loss). Inputs are numpy; standardisation is fit on train."""
    torch.manual_seed(0)
    vlo = int(lo + (1 - val_frac) * (hi - lo))
    Xt = torch.tensor(X[:, lo:hi], dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True); sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (torch.tensor(X[:, lo:vlo], dtype=torch.float32) - mu) / sd
    ftr = torch.tensor(fwd[:, lo:vlo], dtype=torch.float32)
    Xv = (torch.tensor(X[:, vlo:hi], dtype=torch.float32) - mu) / sd
    fv = torch.tensor(fwd[:, vlo:hi], dtype=torch.float32)

    net = DeepMomentumNetwork(X.shape[2], hidden, dropout)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=wd)
    best, best_state = float("inf"), None
    for e in range(epochs):
        net.train(); opt.zero_grad()
        sharpe_loss(net(Xtr), ftr).backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if e % 10 == 0:
            net.eval()
            with torch.no_grad():
                v = float(sharpe_loss(net(Xv), fv))
            if v < best:
                best = v
                best_state = {k: val.clone() for k, val in net.state_dict().items()}
    net.load_state_dict(best_state); net.eval()
    return net, mu, sd, best


def _predict(net, mu, sd, X, lo, hi):
    with torch.no_grad():
        return net((torch.tensor(X[:, lo:hi], dtype=torch.float32) - mu) / sd).numpy()


def nested_walkforward(X, fwd, fold_bounds, warm=252, grid=GRID, epochs=400):
    """Honest nested walk-forward. fold_bounds = list of (train_hi, test_hi); each fold trains
    on [warm, train_hi), selects the config with best VALIDATION loss (never touching test),
    and predicts on [train_hi, test_hi). Returns (POS (N,T) filled on the test spans,
    chosen_configs list, test_index array)."""
    N, T, _ = X.shape
    POS = np.zeros((N, T))
    chosen, test_idx = [], []
    for train_hi, test_hi in fold_bounds:
        best, pick = float("inf"), None
        for cfg in grid:
            net, mu, sd, vloss = _train_fold(X, fwd, warm, train_hi, *cfg, epochs=epochs)
            if vloss < best:
                best, pick, picked = vloss, cfg, (net, mu, sd)
        chosen.append(pick)
        POS[:, train_hi:test_hi] = _predict(*picked, X, train_hi, test_hi)
        test_idx += list(range(train_hi, test_hi))
    return POS, chosen, np.array(test_idx)
