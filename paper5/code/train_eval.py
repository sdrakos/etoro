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
BASE_LR = 1e-3
_SEED = 0
GATE_LOG = []


def set_seed(s):
    """Set the global training seed (model init + RNG). Default 0 reproduces all prior results."""
    global _SEED
    _SEED = int(s)


def _log_gate(net):
    """Diagnostic: record the absolute final gate of a gated model (no-op for models without one)."""
    g = getattr(net, "gate", None)
    if g is not None:
        GATE_LOG.append(abs(float(g.detach())))


def warmup_lambda(step, warmup):
    """LR multiplier: linear 0->1 over `warmup` optimizer steps, then 1.0.
    warmup<=0 -> always 1.0 (no warmup; training path unchanged)."""
    if warmup <= 0:
        return 1.0
    return min(1.0, (step + 1) / warmup)


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


def _prep_tensors(X, fwd, lo, hi, val_frac):
    """Build the standardized train/val tensors for [lo,hi). No RNG (keeps seeding deterministic)."""
    vlo = int(lo + (1 - val_frac) * (hi - lo))
    Xt = torch.tensor(X[:, lo:hi], dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True)
    sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (torch.tensor(X[:, lo:vlo], dtype=torch.float32) - mu) / sd
    ftr = torch.tensor(fwd[:, lo:vlo], dtype=torch.float32)
    Xv = (torch.tensor(X[:, vlo:hi], dtype=torch.float32) - mu) / sd
    fv = torch.tensor(fwd[:, vlo:hi], dtype=torch.float32)
    return mu, sd, Xtr, ftr, Xv, fv


def _run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs, best=float("inf"), best_state=None):
    """Run `epochs` full-batch steps; capture best-validation state every 10 epochs. Threads
    (best, best_state) so a caller can accumulate the best across multiple stages."""
    for e in range(epochs):
        net.train(); opt.zero_grad()
        sharpe_loss(net(Xtr), ftr, cost=TRAIN_COST).backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        sched.step()
        if e % 10 == 0:
            net.eval()
            with torch.no_grad():
                v = float(sharpe_loss(net(Xv), fv, cost=TRAIN_COST))
            if v < best:
                best = v
                best_state = {k: val.clone() for k, val in net.state_dict().items()}
    return best, best_state


def _train_fold(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
    """Train on [lo,hi) with the last val_frac as validation (early stop). Returns (net, mu, sd, best)."""
    torch.manual_seed(_SEED)
    mu, sd, Xtr, ftr, Xv, fv = _prep_tensors(X, fwd, lo, hi, val_frac)
    net = make(X.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, cfg.get("warmup", 0)))
    best, best_state = _run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs)
    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    _log_gate(net)
    return net, mu, sd, best


def _set_requires_grad(net, lstm, attn):
    """Freeze/unfreeze groups of a GatedHybridMomentumNetwork. The head always trains."""
    for p in net.lstm.parameters():
        p.requires_grad_(lstm)
    for p in net.enc.parameters():
        p.requires_grad_(attn)
    net.gate.requires_grad_(attn)
    for p in net.head.parameters():
        p.requires_grad_(True)


def _train_fold_two_stage(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
    """Two-stage training for the gated hybrid: stage 1 trains lstm+head (attention frozen); stage 2
    freezes the lstm and trains attention(enc+gate)+head. Best-val state accumulated ACROSS both
    stages so if stage 2 only hurts, the stage-1 (LSTM) state is kept -> floor is the LSTM."""
    torch.manual_seed(_SEED)
    mu, sd, Xtr, ftr, Xv, fv = _prep_tensors(X, fwd, lo, hi, val_frac)
    net = make(X.shape[2], cfg)
    warmup = cfg.get("warmup", 0)
    e1 = epochs // 2
    e2 = epochs - e1

    _set_requires_grad(net, lstm=True, attn=False)
    opt1 = torch.optim.Adam([p for p in net.parameters() if p.requires_grad],
                            lr=BASE_LR, weight_decay=cfg["wd"])
    sch1 = torch.optim.lr_scheduler.LambdaLR(opt1, lr_lambda=lambda e: warmup_lambda(e, warmup))
    best, best_state = _run_epochs(net, opt1, sch1, Xtr, ftr, Xv, fv, e1)

    _set_requires_grad(net, lstm=False, attn=True)
    opt2 = torch.optim.Adam([p for p in net.parameters() if p.requires_grad],
                            lr=BASE_LR, weight_decay=cfg["wd"])
    sch2 = torch.optim.lr_scheduler.LambdaLR(opt2, lr_lambda=lambda e: warmup_lambda(e, warmup))
    best, best_state = _run_epochs(net, opt2, sch2, Xtr, ftr, Xv, fv, e2, best, best_state)

    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    return net, mu, sd, best


def pretrain_model(make, cfg, X_syn, fwd_syn, epochs=300):
    """Pretrain one model on the FULL synthetic panel and return its state_dict (CPU clones). This is
    a PRIOR (a warm-start), not a selected model -> no val split; we keep the final-epoch weights.
    X_syn (N,T,F), fwd_syn (N,T)."""
    torch.manual_seed(_SEED)
    Xt = torch.tensor(X_syn, dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True)
    sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (Xt - mu) / sd
    ftr = torch.tensor(fwd_syn, dtype=torch.float32)
    net = make(X_syn.shape[2], cfg)
    opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, cfg.get("warmup", 0)))
    _run_epochs(net, opt, sched, Xtr, ftr, Xtr, ftr, epochs)
    net.eval()
    return {k: v.detach().clone() for k, v in net.state_dict().items()}


def make_pretrained_trainer(state):
    """Return a trainer(make, X, fwd, lo, hi, cfg, epochs) that warm-starts from `state`, RESETS the
    scalar gate to 0, then fine-tunes on the real [lo,hi) window exactly like _train_fold."""
    def _trainer(make, X, fwd, lo, hi, cfg, epochs=300, val_frac=0.2):
        torch.manual_seed(_SEED)
        mu, sd, Xtr, ftr, Xv, fv = _prep_tensors(X, fwd, lo, hi, val_frac)
        net = make(X.shape[2], cfg)
        net.load_state_dict(state)
        if hasattr(net, "gate"):
            with torch.no_grad():
                net.gate.zero_()
        opt = torch.optim.Adam(net.parameters(), lr=BASE_LR, weight_decay=cfg["wd"])
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda e: warmup_lambda(e, cfg.get("warmup", 0)))
        best, best_state = _run_epochs(net, opt, sched, Xtr, ftr, Xv, fv, epochs)
        if best_state is not None:
            net.load_state_dict(best_state)
        net.eval()
        _log_gate(net)
        return net, mu, sd, best
    return _trainer


def _predict(net, mu, sd, X, lo, hi):
    with torch.no_grad():
        return net((torch.tensor(X[:, lo:hi], dtype=torch.float32) - mu) / sd).numpy()


def nested_walkforward(make, grid, X, fwd, fold_bounds, warm=252, epochs=300, trainer=None):
    """For each fold, pick the cfg with best validation loss (never touching test), predict on
    the test span. Returns (POS (N,T) filled on test spans only, chosen_cfgs, test_idx)."""
    trainer = trainer or _train_fold
    N, T, _ = X.shape
    POS = np.zeros((N, T))
    chosen, test_idx = [], []
    for train_hi, test_hi in fold_bounds:
        best, pick, picked = float("inf"), None, None
        for cfg in grid:
            net, mu, sd, vloss = trainer(make, X, fwd, warm, train_hi, cfg, epochs)
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
