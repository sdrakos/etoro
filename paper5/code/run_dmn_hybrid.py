#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iteration 2: does attention ON TOP OF the LSTM (the real Momentum Transformer) beat the LSTM-DMN
alone? Runs fixed-rule / LSTM-DMN / pure-Transformer / hybrid on the combined 18-asset basket, both
bands, leak-free nested WF, net @10bps, PPY=252. Prints the table and saves fig_dmn_hybrid.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252


def fixed_rule_baseline(close, dates_ms):
    ret = close.pct_change()
    vol = ret.rolling(30).std() * np.sqrt(PPY)
    pos = (np.sign(close.pct_change(120)) * (0.15 / vol.shift(1))).clip(-2, 2).fillna(0.0)
    pos = pos.ewm(span=5, min_periods=1).mean()
    from band_eval import apply_band
    W = apply_band(pos.values, 0.3) / close.shape[1]
    fwd = ret.shift(-1).values
    m = np.isfinite(fwd).all(axis=1)
    net = costs.net_returns(W[m], fwd[m], 10.0, 0.0)
    d = np.asarray(dates_ms)[m]
    fin = np.isfinite(net); net, d = net[fin], d[fin]
    return {"net_ir": metrics.ann_ir(net, PPY), "nw_t": metrics.newey_west_t(net),
            "dsr": metrics.deflated_sharpe(net, 1, PPY),
            "durability": metrics.durability_by_year(net, d, PPY), "n": len(net)}


def _row(name, band, r):
    y2022 = r["durability"].get(2022)
    pos2022 = "yes" if (y2022 is not None and y2022 > 0) else ("no" if y2022 is not None else "n/a")
    return (name, band, r["net_ir"], r["nw_t"], r["dsr"], pos2022)


def main():
    close = combined_data.fetch_combined_daily()
    X, fwd, dates_ms = crypto_features.build(close)
    T = X.shape[1]
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {close.shape[1]} assets, {T} bars, {close.index[0].date()}..{close.index[-1].date()}")
    print(f"[wf] {len(folds)} folds, test from idx {folds[0][0]}")

    rows = [_row("fixed-rule", "hard", fixed_rule_baseline(close, dates_ms))]

    for name, make, grid in [("LSTM-DMN", models.make_lstm, models.LSTM_GRID),
                             ("pure-Transf", models.make_transformer, models.TRANSF_GRID),
                             ("hybrid", models.make_hybrid, models.HYBRID_GRID)]:
        POS, chosen, test_idx = train_eval.nested_walkforward(
            make, grid, X, fwd, folds, warm=252, epochs=300)
        for band, tag in [(0.0, "none"), (0.3, "hard")]:
            r = train_eval.evaluate(POS, fwd, dates_ms, test_idx, band,
                                    spread_bps=10.0, n_trials=len(grid), ppy=PPY)
            rows.append(_row(name, tag, r))

    print(f"\n{'model':<13}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'+2022':>8}")
    print("-" * 51)
    for nm, bd, ir, t, dsr, y in rows:
        print(f"{nm:<13}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{y:>8}")

    lstm_best = max(r[2] for r in rows if r[0] == "LSTM-DMN")
    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    palette = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb",
               "pure-Transf": "#f59e0b", "hybrid": "#16a34a"}
    ax.bar(labels, irs, color=[palette[r[0]] for r in rows])
    ax.axhline(lstm_best, ls="--", color="#2563eb", lw=1, label=f"LSTM best {lstm_best:.2f}")
    ax.set_ylabel("net IR @10bps"); ax.set_title("Hybrid vs LSTM vs pure-Transformer (combined 18, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_hybrid.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_hybrid.png")


if __name__ == "__main__":
    main()
