"""The two sequence encoders for the crypto DMN. The LSTM is paper4's DeepMomentumNetwork
(imported, unchanged). The MomentumTransformer is a low-capacity causal Transformer with the
same I/O (x (N,T,F) -> positions (N,T) in [-1,1]). Both are built via a uniform
factory(n_features, cfg) so the training loop is model-agnostic and the comparison is fair."""
from __future__ import annotations
import sys, os, math
import torch
import torch.nn as nn
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
from dmn import DeepMomentumNetwork  # paper4 LSTM

# cfg dicts. 'wd' is the optimizer weight_decay (read by train_eval).
LSTM_GRID = [
    {"hidden": 16, "wd": 1e-3, "dropout": 0.0},
    {"hidden": 16, "wd": 1e-2, "dropout": 0.3},
    {"hidden": 8,  "wd": 1e-2, "dropout": 0.3},
    {"hidden": 8,  "wd": 1e-3, "dropout": 0.4},
    {"hidden": 4,  "wd": 1e-2, "dropout": 0.3},
]
TRANSF_GRID = [
    {"d_model": 16, "nheads": 2, "dropout": 0.1, "wd": 1e-3},
    {"d_model": 16, "nheads": 2, "dropout": 0.3, "wd": 1e-2},
    {"d_model": 8,  "nheads": 2, "dropout": 0.3, "wd": 1e-2},
]


class _PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=6000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div[: pe[:, 1::2].shape[1]])
        self.register_buffer("pe", pe)

    def forward(self, x):                # x (N,T,d_model)
        return x + self.pe[: x.size(1)].unsqueeze(0)


class MomentumTransformer(nn.Module):
    """Block-local causal Transformer. The time axis is split into non-overlapping blocks of
    `window` steps; causal attention runs WITHIN each block only. This makes compute O(T*window)
    instead of O(T^2) — full attention over a ~4000-day history is both too slow on CPU and
    needless (the input features already encode horizons up to 252d). Leak-free: a position never
    attends to the future (causal mask), and blocks earlier in time are never seen ahead of time."""
    def __init__(self, n_features, d_model=16, nheads=2, dropout=0.1, nlayers=1, window=256):
        super().__init__()
        self.window = window
        self.proj = nn.Linear(n_features, d_model)
        self.pos = _PositionalEncoding(d_model)
        layer = nn.TransformerEncoderLayer(d_model, nheads, dim_feedforward=4 * d_model,
                                           dropout=dropout, batch_first=True)
        self.enc = nn.TransformerEncoder(layer, nlayers)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x):                # x (N,T,F) -> (N,T) in [-1,1]
        N, T, _ = x.shape
        W = self.window
        h = self.proj(x)                                  # (N,T,d)
        pad = (W - T % W) % W                             # right-pad time to a multiple of W
        if pad:
            h = torch.cat([h, h.new_zeros(N, pad, h.size(-1))], dim=1)
        nb = (T + pad) // W
        h = h.reshape(N * nb, W, -1)                      # contiguous time blocks, block-local
        h = self.pos(h)                                   # positional encoding within the block
        mask = torch.triu(torch.full((W, W), float("-inf"), device=x.device), diagonal=1)
        h = self.enc(h, mask=mask)                        # causal within block, O(W^2) per block
        h = h.reshape(N, T + pad, -1)[:, :T]              # drop the padding
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)


def make_lstm(n_features, cfg):
    return DeepMomentumNetwork(n_features, hidden=cfg["hidden"], dropout=cfg["dropout"])


def make_transformer(n_features, cfg):
    return MomentumTransformer(n_features, d_model=cfg["d_model"], nheads=cfg["nheads"],
                               dropout=cfg["dropout"], window=cfg.get("window", 256))
