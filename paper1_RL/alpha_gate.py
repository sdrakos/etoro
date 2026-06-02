# paper1_RL/alpha_gate.py
"""Fundamental Law of Active Management gate: IR = IC * sqrt(BR) * TC.
Γενικευση του ic_analysis.py — δεχεται αυθαιρετο signal matrix (T,N).
Acceptance: IC_t > 2 (στατιστικα σημαντικο forecasting skill, OOS)."""
from __future__ import annotations
import numpy as np

DELTA = 0.0005  # 5 bps

def _fwd_ret(close, t, hold):
    return close[t + hold] / close[t] - 1

def evaluate(signal: np.ndarray, close: np.ndarray, hold: int = 21,
             oos_frac: float = 0.30) -> dict:
    """signal,(T,N)· OOS μονο. Επιστρεφει IC/IR decomposition + long-short decile."""
    T, N = close.shape
    starts = np.arange(252, T - hold, hold)
    split = int((1 - oos_frac) * len(starts))
    oos = starts[split:]
    ics, ls = [], []
    for t in oos:
        s = signal[t]; f = _fwd_ret(close, t, hold)
        ok = np.isfinite(s) & np.isfinite(f)
        if ok.sum() < 20: continue
        s_, f_ = s[ok], f[ok]
        sd = s_.std(); fsd = f_.std()
        if sd < 1e-12 or fsd < 1e-12: continue          # αποφυγη nan IC απο zero-variance
        ics.append(np.corrcoef((s_ - s_.mean()) / sd, f_)[0, 1])
        k = max(3, int(0.1 * len(s_))); o = np.argsort(s_)
        ls.append(f_[o[-k:]].mean() - f_[o[:k]].mean() - 2 * DELTA)
    ic = np.array(ics); ls = np.array(ls)
    if len(ic) == 0:
        return dict(IC=0.0, IC_t=0.0, predIR=0.0, realIR=0.0, TC=0.0, ls_ann=0.0, n=0)
    reb = 252 / hold
    icbar = ic.mean()
    predIR = icbar * np.sqrt(N * reb)
    realIR = ls.mean() / (ls.std() + 1e-9) * np.sqrt(reb)
    return dict(IC=icbar, IC_t=icbar / (ic.std() + 1e-9) * np.sqrt(len(ic)),
                predIR=predIR, realIR=realIR,
                TC=(realIR / predIR if predIR else 0.0),
                ls_ann=ls.mean() * reb, n=len(ic))

def passes(res: dict, t_thresh: float = 2.0) -> bool:
    return abs(res["IC_t"]) > t_thresh
