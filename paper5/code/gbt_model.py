"""Gradient-boosted-trees (sklearn HistGradientBoostingRegressor) on the 10 belief-state features —
a non-deep, lower-capacity alternative to the transformer/DMN. Leak-free walk-forward: per fold, fit
on the past, select the config by validation IR, refit, predict the test span, and map the predicted
next-day return to a vol-scaled position (same sizing as the fixed rule). Reuses evaluate() downstream."""
from __future__ import annotations
import sys, os
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import metrics  # paper4

GBT_GRID = [
    {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 100, "l2_regularization": 1.0},
    {"max_iter": 300, "learning_rate": 0.03, "max_leaf_nodes": 31, "min_samples_leaf": 200, "l2_regularization": 1.0},
    {"max_iter": 200, "learning_rate": 0.05, "max_leaf_nodes": 7,  "min_samples_leaf": 300, "l2_regularization": 2.0},
]
TARGET_VOL = 0.15


def predict_to_position(pred, vol, scale):
    """Map predicted return(s) to a vol-scaled position in [-2,2]. direction = tanh(pred/scale);
    position = clip(direction * (TARGET_VOL/vol), -2, 2). Works elementwise on arrays of any shape."""
    direction = np.tanh(np.asarray(pred, float) / (scale + 1e-12))
    pos = direction * (TARGET_VOL / np.maximum(np.asarray(vol, float), 1e-6))
    return np.clip(pos, -2.0, 2.0)


def _flatten(X, fwd, lo, hi):
    """(N,T,F)+(N,T) over [lo,hi) -> rows (M,F), targets (M,), dropping non-finite rows."""
    Xr = X[:, lo:hi].reshape(-1, X.shape[2])
    yr = fwd[:, lo:hi].reshape(-1)
    m = np.isfinite(Xr).all(axis=1) & np.isfinite(yr)
    return Xr[m], yr[m]


def _ewm_rows(pos, span=5):
    """Per-asset EWM smoothing along time. pos (N, L) -> (N, L)."""
    return pd.DataFrame(pos.T).ewm(span=span, min_periods=1).mean().to_numpy().T


def _span_positions(model, X, vol, lo, hi, scale):
    """Predict [lo,hi) and map to positions (N, hi-lo) (no smoothing — used for val IR)."""
    N, _, F = X.shape
    pred = model.predict(X[:, lo:hi].reshape(-1, F)).reshape(N, hi - lo)
    return predict_to_position(pred, vol[:, lo:hi], scale)


def gbt_positions(X, fwd, vol, fold_bounds, grid=GBT_GRID, warm=252):
    """Leak-free GBT walk-forward. Returns (POS (N,T) filled on test spans only, test_idx)."""
    N, T, F = X.shape
    POS = np.zeros((N, T))
    test_idx = []
    for train_hi, test_hi in fold_bounds:
        vlo = int(warm + 0.8 * (train_hi - warm))
        Xtr, ytr = _flatten(X, fwd, warm, vlo)
        best_ir, best_cfg = -1e18, None
        for cfg in grid:
            m = HistGradientBoostingRegressor(random_state=0, **cfg).fit(Xtr, ytr)
            s = float(np.std(m.predict(Xtr))) + 1e-9
            pos_val = _span_positions(m, X, vol, vlo, train_hi, s)
            port = np.nanmean(pos_val * fwd[:, vlo:train_hi], axis=0)
            port = port[np.isfinite(port)]
            ir = metrics.ann_ir(port, 252) if len(port) else -1e18
            if np.isfinite(ir) and ir > best_ir:
                best_ir, best_cfg = ir, cfg
        if best_cfg is None:
            best_cfg = grid[0]
        Xall, yall = _flatten(X, fwd, warm, train_hi)
        model = HistGradientBoostingRegressor(random_state=0, **best_cfg).fit(Xall, yall)
        s = float(np.std(model.predict(Xall))) + 1e-9
        pos = _span_positions(model, X, vol, train_hi, test_hi, s)
        POS[:, train_hi:test_hi] = np.nan_to_num(_ewm_rows(pos, span=5))
        test_idx += list(range(train_hi, test_hi))
    return POS, np.array(test_idx)
