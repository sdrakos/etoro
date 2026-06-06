"""paper4 headline run: rules vs ML (LSTM Deep Momentum Network) vs buy-and-hold, on the
diversified ETF basket, honest nested out-of-sample, net of costs. Writes results.json and
the backtest figures used in the paper."""
from __future__ import annotations
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timezone

from etf_data import load_etf_matrix
from features import build_features
from dmn import nested_walkforward, GRID
from ts_momentum import build_ts_weights
from costs import net_returns
from metrics import newey_west_t, deflated_sharpe

FIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))


def _scale(r, target=0.10):
    return r * (target / (r.std() * np.sqrt(252) + 1e-12))


def _stats(r):
    eq = 10000 * np.cumprod(1 + r)
    return {"final": float(eq[-1]),
            "cagr": float((eq[-1] / 10000) ** (252 / len(r)) - 1),
            "maxdd": float((eq / np.maximum.accumulate(eq) - 1).min()),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252))}, eq


def main():
    close, dates, tickers = load_etf_matrix()
    T, N = close.shape
    years = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc).year for m in dates])
    d = np.array([datetime.fromtimestamp(int(m) / 1000, tz=timezone.utc) for m in dates])

    # --- ML: honest nested walk-forward (folds end-2016, end-2020) ---
    X, fwd = build_features(close)
    f1 = np.where(years == 2016)[0][-1]; f2 = np.where(years == 2020)[0][-1]
    POS, chosen, oos = nested_walkforward(X, fwd, [(f1, f2), (f2, T)], warm=252)
    ml_port = (POS * fwd).sum(0) / N
    ml_turn = np.zeros(T); ml_turn[1:] = np.abs(POS[:, 1:] - POS[:, :-1]).sum(0) / N
    ml_net = (ml_port - 5e-4 * ml_turn)[oos]

    # --- rules baseline over the SAME out-of-sample span ---
    W = build_ts_weights(close)
    fwdTN = np.zeros((T, N)); fwdTN[:-1] = close[1:] / close[:-1] - 1.0
    ru_net = net_returns(W, fwdTN, spread_bps=5.0, short_fin_bps_annual=0.0)[oos]

    spy = (close[1:, tickers.index("SPY")] / close[:-1, tickers.index("SPY")] - 1.0)
    spy = np.concatenate([[0.0], spy])[oos]
    do = d[oos]

    ml, ru = _scale(ml_net), _scale(ru_net)
    series = {"Buy&hold SPY": spy, "Rules trend": ru, "ML LSTM trend": ml,
              "50% SPY + 50% ML": 0.5 * spy + 0.5 * ml, "100% SPY + 50% ML overlay": spy + 0.5 * ml}

    results = {"oos_start": str(do[0].date()), "oos_end": str(do[-1].date()),
               "n_tickers": N, "chosen_configs": chosen,
               "ml_nw_t": float(newey_west_t(ml, 21)),
               "ml_dsr": float(deflated_sharpe(ml, n_trials=len(GRID)))}
    print(f"OOS {results['oos_start']}..{results['oos_end']}  ({N} ETFs)  net of costs")
    print(f"ML auto-selected configs (by validation): {chosen}")
    print(f"ML  NW-t={results['ml_nw_t']:+.2f}  DSR={results['ml_dsr']:.2f}\n")
    eqs = {}
    for name, r in series.items():
        s, eq = _stats(r); eqs[name] = eq; results[name] = s
        print(f"{name:<28} EUR {s['final']:>9,.0f}  CAGR {s['cagr']*100:>+5.1f}%  "
              f"maxDD {s['maxdd']*100:>+5.0f}%  Sharpe {s['sharpe']:.2f}")

    os.makedirs(FIG, exist_ok=True)
    # fig 1: ML vs rules vs SPY
    plt.figure(figsize=(11, 6))
    for k, c in [("Buy&hold SPY", "gray"), ("Rules trend", "orange"), ("ML LSTM trend", "blue")]:
        plt.plot(do, eqs[k], label=k, lw=2 if "ML" in k else 1.3, color=c)
    plt.title("EUR 10,000 out-of-sample: ML LSTM vs Rules vs SPY")
    plt.ylabel("EUR"); plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
    plt.savefig(f"{FIG}/etf_ml_vs_rules.png", dpi=130); plt.close()
    # fig 2: beat buy & hold
    plt.figure(figsize=(11, 6))
    for k in ["Buy&hold SPY", "ML LSTM trend", "50% SPY + 50% ML", "100% SPY + 50% ML overlay"]:
        plt.plot(do, eqs[k], label=k, lw=2.2 if "overlay" in k else 1.4)
    plt.title("EUR 10,000 out-of-sample: beating buy & hold by combining (return stacking)")
    plt.ylabel("EUR"); plt.legend(fontsize=8); plt.grid(alpha=.3); plt.tight_layout()
    plt.savefig(f"{FIG}/etf_beat_buyhold.png", dpi=130); plt.close()

    with open(os.path.join(FIG, "..", "results_etf.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved figures/etf_ml_vs_rules.png, figures/etf_beat_buyhold.png, results_etf.json")


if __name__ == "__main__":
    main()
