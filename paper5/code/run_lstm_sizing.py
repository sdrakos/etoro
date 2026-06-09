#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yahoo 5-asset sweep: does vol-target sizing on the LSTM signal raise its risk-adjusted profit?
Compares raw-LSTM / LSTM+vol-target {0.10,0.15,0.30} / fixed-rule on the diversified 5-asset sweet
spot (SPY/TLT/GLD/BTC-USD/UUP), leak-free, net @10bps, hard band. Reports IR, annualized %, maxDD,
and realized vol (to read profit at matched risk). Saves fig_lstm_sizing.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models, band_eval, lstm_sizing

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
FIVE = ["SPY", "TLT", "GLD", "BTC-USD", "UUP"]


def _rule_positions(df):
    ret = df.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(PPY)
    pos = (np.sign(df.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
    return pos.ewm(span=5, min_periods=1).mean().to_numpy().T


def _metrics(POS, fwd, idx, band, n_trials):
    N = POS.shape[0]
    W = band_eval.apply_band(POS.T, band) / N
    net = costs.net_returns(W[np.asarray(idx)], np.asarray(fwd).T[np.asarray(idx)], 10.0, 0.0)
    net = net[np.isfinite(net)]
    eq = float(np.prod(1.0 + net))
    ann = eq ** (PPY / len(net)) - 1.0
    return {"ir": metrics.ann_ir(net, PPY), "ann": ann, "mdd": metrics.max_drawdown(net),
            "vol": float(np.std(net) * np.sqrt(PPY)),
            "dsr": metrics.deflated_sharpe(net, n_trials, PPY)}


def main():
    df = combined_data.fetch_combined_daily()[FIVE].dropna(how="any")
    X, fwd, dates_ms = crypto_features.build(df)
    T = X.shape[1]
    vol = (df.pct_change().rolling(30).std() * np.sqrt(PPY)).shift(1).to_numpy().T
    vol = np.nan_to_num(vol, nan=1.0)
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {len(FIVE)} assets {FIVE}, {T} bars {df.index[0].date()}..{df.index[-1].date()}, folds={len(folds)}")

    POS_l, _, idx = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds,
                                                  warm=252, epochs=300)
    POS_r = _rule_positions(df)
    nL = len(models.LSTM_GRID)

    rows = [("LSTM raw", _metrics(POS_l, fwd, idx, 0.3, nL))]
    for tv in (0.10, 0.15, 0.30):
        rows.append((f"LSTM vt{tv:.2f}", _metrics(lstm_sizing.size_positions(POS_l, vol, tv), fwd, idx, 0.3, nL)))
    rows.append(("fixed-rule", _metrics(POS_r, fwd, idx, 0.3, 1)))

    print(f"\n{'variant':<14}{'netIR':>8}{'ann%':>8}{'maxDD':>8}{'realVol':>9}{'DSR':>7}")
    print("-" * 54)
    for nm, m in rows:
        print(f"{nm:<14}{m['ir']:>8.2f}{m['ann']*100:>7.1f}%{m['mdd']:>8.0%}{m['vol']*100:>8.1f}%{m['dsr']:>7.2f}")

    fig, ax = plt.subplots(figsize=(10, 4.6))
    labels = [nm for nm, _ in rows]
    ax.bar(labels, [m["ir"] for _, m in rows], color="#2563eb")
    ax.axhline(rows[-1][1]["ir"], ls="--", color="#64748b", lw=1, label=f"rule IR {rows[-1][1]['ir']:.2f}")
    ax.set_ylabel("net IR @10bps"); ax.set_title("LSTM + vol-target sizing sweep (Yahoo 5-asset, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_lstm_sizing.png"), dpi=130); plt.close()
    print("\n[fig] figures/fig_lstm_sizing.png")


if __name__ == "__main__":
    main()
