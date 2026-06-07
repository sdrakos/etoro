"""Model-agnostic, leak-free nested walk-forward for the crypto DMN, plus net-of-cost evaluation.
Mirrors paper4's dmn.nested_walkforward but takes a model factory + cfg-dict grid so the LSTM and
the Transformer share one identical training loop (fair comparison). Training charges a 10 bps
turnover penalty in the Sharpe loss; the hard no-trade band is applied separately at serve."""
from __future__ import annotations
import sys, os
import numpy as np
import torch
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
from dmn import sharpe_loss
import band_eval

PPY = 365                 # crypto trades 24/7
TRAIN_COST = 1e-3         # 10 bps turnover penalty inside the training loss


def make_folds(T, warm=252, first_train=1500, step=252):
    """Expanding-train, tiling-test folds. Returns [(train_hi, test_hi), ...] with contiguous
    test spans starting at first_train. A trailing span shorter than 20 bars is dropped."""
    folds = []
    train_hi = first_train
    while train_hi < T:
        test_hi = min(train_hi + step, T)
        if test_hi - train_hi < 20:
            break
        folds.append((train_hi, test_hi))
        train_hi = test_hi
    return folds


def _train_fold(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
    """Train one model on [lo,hi) with the last val_frac as validation (early stop on it).
    Standardisation fit on train only. Returns (net, mu, sd, best_val_loss)."""
    torch.manual_seed(0)
    vlo = int(lo + (1 - val_frac) * (hi - lo))
    Xt = torch.tensor(X[:, lo:hi], dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True)
    sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (torch.tensor(X[:, lo:vlo], dtype=torch.float32) - mu) / sd
    ftr = torch.tensor(fwd[:, lo:vlo], dtype=torch.float32)
    Xv = (torch.tensor(X[:, vlo:hi], dtype=torch.float32) - mu) / sd
    fv = torch.tensor(fwd[:, vlo:hi], dtype=torch.float32)

    net = make(X.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=cfg["wd"])
    best, best_state = float("inf"), None
    for e in range(epochs):
        net.train(); opt.zero_grad()
        sharpe_loss(net(Xtr), ftr, cost=TRAIN_COST).backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if e % 10 == 0:
            net.eval()
            with torch.no_grad():
                v = float(sharpe_loss(net(Xv), fv, cost=TRAIN_COST))
            if v < best:
                best = v
                best_state = {k: val.clone() for k, val in net.state_dict().items()}
    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    return net, mu, sd, best


def _predict(net, mu, sd, X, lo, hi):
    with torch.no_grad():
        return net((torch.tensor(X[:, lo:hi], dtype=torch.float32) - mu) / sd).numpy()


def nested_walkforward(make, grid, X, fwd, fold_bounds, warm=252, epochs=300):
    """For each fold, pick the cfg with best validation loss (never touching test), predict on
    the test span. Returns (POS (N,T) filled on test spans only, chosen_cfgs, test_idx)."""
    N, T, _ = X.shape
    POS = np.zeros((N, T))
    chosen, test_idx = [], []
    for train_hi, test_hi in fold_bounds:
        best, pick, picked = float("inf"), None, None
        for cfg in grid:
            net, mu, sd, vloss = _train_fold(make, X, fwd, warm, train_hi, cfg, epochs)
            if vloss < best:
                best, pick, picked = vloss, cfg, (net, mu, sd)
        chosen.append(pick)
        POS[:, train_hi:test_hi] = _predict(*picked, X, train_hi, test_hi)
        test_idx += list(range(train_hi, test_hi))
    return POS, chosen, np.array(test_idx)


def evaluate(POS, fwd, dates_ms, test_idx, band, spread_bps=10.0, n_trials=1, short_fin=0.0, ppy=PPY):
    """Apply the band to the full (T,N) path, slice to test rows, charge costs, return metrics.
    POS, fwd are (N,T); net_returns wants (T,N) so we transpose. `ppy` = periods/year for
    annualisation (365 for 24/7 crypto, 252 for a weekday calendar)."""
    W_full = band_eval.apply_band(POS.T, band) / POS.shape[0]   # (T,N), equal capital
    F_full = np.asarray(fwd).T                                  # (T,N)
    rows = np.asarray(test_idx)
    net = costs.net_returns(W_full[rows], F_full[rows], spread_bps, short_fin)
    fin = np.isfinite(net)
    net = net[fin]
    d = np.asarray(dates_ms)[rows][fin]
    return {
        "net_ir": metrics.ann_ir(net, ppy),
        "nw_t": metrics.newey_west_t(net),
        "dsr": metrics.deflated_sharpe(net, n_trials=n_trials, periods=ppy),
        "durability": metrics.durability_by_year(net, d, ppy),
        "n": len(net),
    }
