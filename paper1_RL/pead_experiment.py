# paper1_RL/pead_experiment.py
"""(A) PEAD / earnings-surprise drift. Gate -> long-short + DER overlay.
Building blocks: yahoo_research_data, signals, alpha_gate (ολα tested)."""
import numpy as np
import yahoo_research_data as Y
import signals as S
from alpha_gate import evaluate, passes

WINDOW = 60   # drift window σε trading days

def build_surprise_signal(d):
    close = d["close"]; T, N = close.shape
    earn = d["earnings"]                                 # {int: [(date_idx, surp), ...]}
    M = Y.surprise_matrix(np.arange(T), earn, n=N, window=WINDOW)
    # cross-sectional z-score ανα μερα (relative surprise)
    Z = np.full_like(M, np.nan)
    for t in range(T):
        if np.isfinite(M[t]).sum() >= 5:
            Z[t] = S.zscore_xs(M[t])
    return Z

def main():
    d = Y.load_universe()
    close = d["close"]; vix = d["vix"]
    Z = build_surprise_signal(d)

    res = evaluate(signal=Z, close=close, hold=21)
    print("=== (A) PEAD surprise — Fundamental-Law gate (OOS) ===")
    print(f"IC={res['IC']:.4f}  t={res['IC_t']:.2f}  predIR={res['predIR']:.2f}  "
          f"realIR={res['realIR']:.2f}  TC={res['TC']:.2f}  n={res['n']}")
    if not passes(res):
        print(">> ΑΠΟΡΡΙΨΗ: IC_t<=2 — κανενα alpha claim (τιμια αναφορα).")
        return
    print(">> PASS: στατιστικα σημαντικο σημα -> strategy backtest.")

    # long-short market-neutral με DER vol-target (VIX-driven θ) overlay
    T, N = close.shape
    ret = np.zeros_like(close); ret[1:] = close[1:] / close[:-1] - 1
    vix_ref = np.nanmedian(vix[:int(0.7*T)])
    Rs = []
    days = np.arange(252, T - 1)
    split = int(0.7 * len(days))
    for t in days[split:]:
        s = Z[t]
        if np.isfinite(s).sum() < 10: Rs.append(0.0); continue
        w = np.nan_to_num(s); w = w / (np.nansum(np.abs(w)) + 1e-9)   # mkt-neutral, gross 1
        w = S.vix_theta_scale(w, vix[t], vix_ref)
        Rs.append(np.nansum(w * ret[t + 1]) - 0.0005 * np.nansum(np.abs(w)))
    R = np.array(Rs); eq = np.cumprod(1 + R)
    dn = R[R < 0]
    print(f"Strategy OOS: ret={eq[-1]-1:.1%}  Sharpe={R.mean()/(R.std()+1e-9)*np.sqrt(252):.2f}"
          f"  Sortino={R.mean()/(dn.std()+1e-9)*np.sqrt(252):.2f}"
          f"  MaxDD={np.min(eq/np.maximum.accumulate(eq)-1):.1%}")

if __name__ == "__main__":
    main()
