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


def _block_local_encode(enc, pos, h, window):
    """Block-local causal Transformer encode of an already-embedded sequence h (N,T,d).
    Splits time into non-overlapping blocks of `window`, runs causal attention WITHIN each block
    (O(T*window), leak-free), and returns (N,T,d). Shared by MomentumTransformer and the hybrid."""
    N, T, d = h.shape
    W = window
    pad = (W - T % W) % W
    if pad:
        h = torch.cat([h, h.new_zeros(N, pad, d)], dim=1)
    nb = (T + pad) // W
    h = h.reshape(N * nb, W, d)
    h = pos(h)
    mask = torch.triu(torch.full((W, W), float("-inf"), device=h.device), diagonal=1)
    h = enc(h, mask=mask)
    return h.reshape(N, T + pad, d)[:, :T]


class MomentumTransformer(nn.Module):
    """Block-local causal Transformer. The time axis is split into non-overlapping blocks of
    `window` steps; causal attention runs WITHIN each block only. This makes compute O(T*window)
    instead of O(T^2) — full attention over a ~4000-day history is both too slow on CPU and
    needless (the input features already encode horizons up to 252d). Leak-free: a position never
    attends to the future (causal mask), and blocks earlier in time are never seen ahead of time."""
    def __init__(self, n_features, d_model=16, nheads=2, dropout=0.1, nlayers=1, window=256, norm_first=False):
        super().__init__()
        self.window = window
        self.proj = nn.Linear(n_features, d_model)
        self.pos = _PositionalEncoding(d_model)
        layer = nn.TransformerEncoderLayer(d_model, nheads, dim_feedforward=4 * d_model,
                                           dropout=dropout, batch_first=True, norm_first=norm_first)
        self.enc = nn.TransformerEncoder(layer, nlayers)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x):                # x (N,T,F) -> (N,T) in [-1,1]
        h = _block_local_encode(self.enc, self.pos, self.proj(x), self.window)
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)


class HybridMomentumNetwork(nn.Module):
    """The real Momentum Transformer (Wood 2022): an LSTM encoder whose hidden-state sequence is then
    refined by pre-LN block-local causal attention. The LSTM carries long memory and gives the model
    its sample efficiency; the attention adds 'look back at the relevant regime'. Same I/O as the
    other models. Leak-free: LSTM is causal and the attention is block-local causal."""
    def __init__(self, n_features, hidden=16, nheads=2, dropout=0.1, nlayers=1, window=256):
        super().__init__()
        self.window = window
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.pos = _PositionalEncoding(hidden)
        layer = nn.TransformerEncoderLayer(hidden, nheads, dim_feedforward=4 * hidden,
                                           dropout=dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, nlayers)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):                # x (N,T,F) -> (N,T) in [-1,1]
        h, _ = self.lstm(x)
        h = _block_local_encode(self.enc, self.pos, h, self.window)
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)


class GatedHybridMomentumNetwork(nn.Module):
    """Like the hybrid, but attention is a SCALAR-GATED RESIDUAL: out = h + g * attention(h), where
    g is a single learnable scalar initialized to 0. At init g=0 so the model IS an LSTM->head
    (~the 0.92 model) with attention invisible; training raises g only if attention helps. Floor is
    the LSTM, upside only. Leak-free: LSTM causal + block-local-causal attention."""
    def __init__(self, n_features, hidden=16, nheads=2, dropout=0.1, window=256):
        super().__init__()
        self.window = window
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.pos = _PositionalEncoding(hidden)
        layer = nn.TransformerEncoderLayer(hidden, nheads, dim_feedforward=4 * hidden,
                                           dropout=dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, 1)
        self.gate = nn.Parameter(torch.zeros(1))
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):                # x (N,T,F) -> (N,T) in [-1,1]
        h, _ = self.lstm(x)
        a = _block_local_encode(self.enc, self.pos, h, self.window)
        h = h + self.gate * a
        return torch.tanh(self.head(self.drop(h))).squeeze(-1)


def make_lstm(n_features, cfg):
    return DeepMomentumNetwork(n_features, hidden=cfg["hidden"], dropout=cfg["dropout"])


def make_transformer(n_features, cfg):
    return MomentumTransformer(n_features, d_model=cfg["d_model"], nheads=cfg["nheads"],
                               dropout=cfg["dropout"], window=cfg.get("window", 256),
                               norm_first=cfg.get("norm_first", False))


HYBRID_GRID = [
    {"hidden": 16, "nheads": 2, "dropout": 0.1, "wd": 1e-3, "warmup": 50},
    {"hidden": 16, "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
    {"hidden": 8,  "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
]


def make_hybrid(n_features, cfg):
    return HybridMomentumNetwork(n_features, hidden=cfg["hidden"], nheads=cfg["nheads"],
                                 dropout=cfg["dropout"], window=cfg.get("window", 256))


GATED_GRID = [
    {"hidden": 16, "nheads": 2, "dropout": 0.1, "wd": 1e-3, "warmup": 50},
    {"hidden": 16, "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
    {"hidden": 8,  "nheads": 2, "dropout": 0.3, "wd": 1e-2, "warmup": 50},
]


def make_gated_hybrid(n_features, cfg):
    return GatedHybridMomentumNetwork(n_features, hidden=cfg["hidden"], nheads=cfg["nheads"],
                                      dropout=cfg["dropout"], window=cfg.get("window", 256))
