#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confirmation experiment: run the full model zoo (rule / LSTM / pure-Transformer / gated attention
/ GBT) on the paper4 18-ETF universe over deep Yahoo history. Tests whether the ETF universe (subtle
trends, long regime-tested history) restores the ML's edge over the rule — vs the crypto setting where
the rule won. Leak-free, net @10bps, both bands. Prints the table and saves fig_etf_zoo.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
from etf_universe import TICKERS as ETF
import crypto_data, crypto_features, train_eval, models, gbt_model, band_eval

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
ETF_CACHE = os.path.join(HERE, "etf18_close.npz")
PPY = 252


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
    return {"ir": metrics.ann_ir(net, PPY), "ann": eq ** (PPY / len(net)) - 1.0,
            "mdd": metrics.max_drawdown(net), "dsr": metrics.deflated_sharpe(net, n_trials, PPY)}


def main():
    close = crypto_data.fetch_crypto_daily(tickers=tuple(ETF), period="20y", cache_path=ETF_CACHE).dropna(how="any")
    X, fwd, dates_ms = crypto_features.build(close)
    T = X.shape[1]
    vol = (close.pct_change().rolling(30).std() * np.sqrt(PPY)).shift(1).to_numpy().T
    vol = np.nan_to_num(vol, nan=1.0)
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {close.shape[1]} ETFs, {T} bars {close.index[0].date()}..{close.index[-1].date()}, folds={len(folds)}")

    POS_r = _rule_positions(close)
    idx_all = np.array([i for lo, hi in folds for i in range(lo, hi)])
    ml = {}
    for name, mk, grid, trainer in [
        ("LSTM-DMN", models.make_lstm, models.LSTM_GRID, None),
        ("pure-Transf", models.make_transformer, models.TRANSF_GRID, None),
        ("gated-attn", models.make_gated_hybrid, models.GATED_GRID, None),
    ]:
        POS, _, idx = train_eval.nested_walkforward(mk, grid, X, fwd, folds, warm=252, epochs=300, trainer=trainer)
        ml[name] = (POS, idx, len(grid))
    POS_g, idx_g = gbt_model.gbt_positions(X, fwd, vol, folds, warm=252)
    ml["GBT"] = (POS_g, idx_g, len(gbt_model.GBT_GRID))

    rows = []
    for band, tag in [(0.0, "none"), (0.3, "hard")]:
        rows.append(("fixed-rule", tag, _metrics(POS_r, fwd, idx_all, band, 1)))
    for name, (POS, idx, ntr) in ml.items():
        for band, tag in [(0.0, "none"), (0.3, "hard")]:
            rows.append((name, tag, _metrics(POS, fwd, idx, band, ntr)))

    print(f"\n{'model':<13}{'band':<6}{'netIR':>8}{'ann%':>8}{'maxDD':>8}{'DSR':>7}")
    print("-" * 50)
    for nm, bd, m in rows:
        print(f"{nm:<13}{bd:<6}{m['ir']:>8.2f}{m['ann']*100:>7.1f}%{m['mdd']:>8.0%}{m['dsr']:>7.2f}")

    pal = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "pure-Transf": "#f59e0b",
           "gated-attn": "#16a34a", "GBT": "#0d9488"}
    labels = [f"{nm}\n{bd}" for nm, bd, _ in rows]
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.bar(labels, [m["ir"] for _, _, m in rows], color=[pal[nm] for nm, _, _ in rows])
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR @10bps"); ax.set_title("Model zoo on the paper4 18-ETF universe (deep Yahoo, OOS net)")
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_etf_zoo.png"), dpi=130); plt.close()
    print("\n[fig] figures/fig_etf_zoo.png")


if __name__ == "__main__":
    main()
