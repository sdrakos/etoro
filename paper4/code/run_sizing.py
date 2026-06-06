"""Apply the position-sizing strategies to the paper4 ETF book and compare, honest OOS, net.
Produces fig_sizing.png (Buy&Hold / Rules / LSTM / bet-optimized) + a sizing comparison table."""
from __future__ import annotations
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timezone

from etf_data import load_etf_matrix
from features import build_features
from dmn import nested_walkforward
from metrics import ann_ir, max_drawdown
from sizing import (ledoit_wolf_cov, inverse_vol_weights, min_variance_weights,
                    hrp_weights, kelly_leverage)

FIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))
plt.rcParams.update({"font.family": "serif", "font.size": 12, "axes.titlesize": 13,
                     "figure.dpi": 150, "axes.grid": True, "grid.alpha": 0.3, "savefig.bbox": "tight"})
GREEN, RED, BLUE, ORANGE, GRAY = "#2a7f4f", "#c0392b", "#1f4e9c", "#e08a1e", "#888888"


def _scale(r, t=0.10):
    return r * (t / (r.std() * np.sqrt(252) + 1e-12))


def _stats(r):
    eq = 10000 * np.cumprod(1 + r)
    return {"final": float(eq[-1]), "cagr": float((eq[-1] / 1e4) ** (252 / len(r)) - 1),
            "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252))}


def sized_book(close, alloc, lookbacks=(21, 63, 126, 252), vol_win=63, rebal=21, cov_win=252):
    """Build a monthly-rebalanced trend book whose per-asset MAGNITUDES come from `alloc(cov)`
    (a risk-budget allocation), times the multi-horizon trend sign. alloc in {inverse_vol, hrp,
    min_variance}. Returns daily net-of-cost returns."""
    T, N = close.shape
    ret = np.zeros((T, N)); ret[1:] = close[1:] / close[:-1] - 1.0
    ret = np.nan_to_num(ret)                          # pre-IPO leading NaNs -> 0 (pre-2008 only)
    fwd = np.zeros((T, N)); fwd[:-1] = ret[1:]
    W = np.zeros((T, N)); cur = np.zeros(N); warm = max(lookbacks)
    for t in range(warm, T):
        if (t - warm) % rebal == 0 and t >= cov_win:
            sign = np.nan_to_num(np.mean([np.sign(close[t] / close[t - lb] - 1.0) for lb in lookbacks], axis=0))
            cov = ledoit_wolf_cov(ret[t - cov_win:t])
            mag = alloc(cov)
            w = sign * mag
            cur = w / (np.sum(np.abs(w)) + 1e-9)
        W[t] = cur
    gross = np.nansum(W * fwd, axis=1)
    turn = np.zeros(T); turn[1:] = np.nansum(np.abs(W[1:] - W[:-1]), axis=1)
    return gross - 5e-4 * turn


def main():
    close, dates, tickers = load_etf_matrix()
    T, N = close.shape
    years = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc).year for m in dates])
    d = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc) for m in dates])

    # ML (honest nested) OOS returns -- cached so sizing tweaks are instant
    X, fwd = build_features(close)
    f1 = np.where(years == 2016)[0][-1]; f2 = np.where(years == 2020)[0][-1]
    cache = os.path.join(os.path.dirname(__file__), "ml_pos_oos.npz")
    if os.path.exists(cache):
        z = np.load(cache); POS, oos = z["POS"], z["oos"]
    else:
        POS, _, oos = nested_walkforward(X, fwd, [(f1, f2), (f2, T)], warm=252)
        np.savez(cache, POS=POS, oos=oos)
    ml_port = (POS * fwd).sum(0) / N
    ml_turn = np.zeros(T); ml_turn[1:] = np.abs(POS[:, 1:] - POS[:, :-1]).sum(0) / N
    ml = _scale((ml_port - 5e-4 * ml_turn)[oos])

    # rules book under 3 allocations
    allocs = {"inverse-vol (baseline)": inverse_vol_weights,
              "HRP": hrp_weights, "min-variance": min_variance_weights}
    alloc_oos = {k: _scale(sized_book(close, fn)[oos]) for k, fn in allocs.items()}
    spy = np.concatenate([[0.0], close[1:, tickers.index("SPY")] / close[:-1, tickers.index("SPY")] - 1.0])[oos]
    do = d[oos]

    # --- print allocation comparison (rules signal) ---
    print("ALLOCATION on the trend signal (OOS, net, scaled to 10% vol):")
    for k, r in alloc_oos.items():
        s = _stats(r); print(f"  {k:<24} Sharpe {s['sharpe']:.2f}  maxDD {s['maxdd']*100:+.0f}%  EUR {s['final']:,.0f}")

    # --- Kelly leverage ladder on the ML book (the 'bet optimization') ---
    # Kelly leverage estimated on the FIRST OOS fold, applied to the SECOND (no look-ahead).
    split = len(oos) // 2
    print("\nKELLY leverage on the ML book (f* from 1st half, applied to 2nd half OOS):")
    kell = {}
    for frac in (0.25, 0.5, 1.0):
        L = kelly_leverage(ml[:split], fraction=frac, cap=2.0)
        kell[frac] = L
        s = _stats(ml * L)
        print(f"  {int(frac*100)}% Kelly (x{L:.1f})   CAGR {s['cagr']*100:+.1f}%  maxDD {s['maxdd']*100:+.0f}%  EUR {s['final']:,.0f}")

    # 'bet-optimized' headline = ML book + quarter-Kelly leverage (the safe, standard choice)
    opt = ml * kell[0.25]

    # --- headline figure: Buy&Hold / Rules / LSTM / bet-optimized ---
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(do, 1e4 * np.cumprod(1 + spy), color=GRAY, lw=1.3, label="Buy & hold SPY")
    ax.plot(do, 1e4 * np.cumprod(1 + alloc_oos["inverse-vol (baseline)"]), color=ORANGE, lw=1.5, label="Rules trend")
    ax.plot(do, 1e4 * np.cumprod(1 + ml), color=BLUE, lw=1.8, label="ML LSTM")
    ax.plot(do, 1e4 * np.cumprod(1 + opt), color=RED, lw=2.4,
            label=f"ML LSTM + bet optimization (quarter-Kelly, x{kell[0.25]:.1f})")
    ax.set_ylabel("Account value (EUR, start 10,000)"); ax.legend(fontsize=9)
    ax.set_title("Out-of-sample, net of costs: rules vs LSTM vs buy-and-hold vs bet-optimized")
    fig.savefig(f"{FIG}/fig_sizing.png"); plt.close(fig)

    out = {"oos": [str(do[0].date()), str(do[-1].date())],
           "allocation": {k: _stats(r) for k, r in alloc_oos.items()},
           "kelly": {f"{int(f*100)}pct": {"leverage": kell[f], **_stats(ml * kell[f])} for f in kell},
           "buyhold_spy": _stats(spy), "ml": _stats(ml), "bet_optimized": _stats(opt)}
    with open(os.path.join(FIG, "..", "results_sizing.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, indent=2)
    print("\nSaved figures/fig_sizing.png and results_sizing.json")


if __name__ == "__main__":
    main()
