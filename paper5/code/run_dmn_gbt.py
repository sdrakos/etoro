#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tabular GBT vs deep LSTM vs fixed rule on real combined-18 (both bands, net @10bps, PPY=252).
The GBT (sklearn HistGradientBoosting) predicts next-day return from the 10 features and is sized with
the same vol-target + band as the rule. Also reports permutation feature importances. Prints the table
and saves fig_dmn_gbt.png."""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import costs, metrics
import combined_data, crypto_features, train_eval, models, gbt_model
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
FEAT_NAMES = ["ret1", "ret21", "ret63", "ret126", "ret252", "logvol",
              "kal_vel", "kal_tsig", "kal_innov", "bocpd"]


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
    vol_nt = (close.pct_change().rolling(30).std() * np.sqrt(PPY)).shift(1).to_numpy().T
    vol_nt = np.nan_to_num(vol_nt, nan=1.0)
    print(f"[data] {close.shape[1]} assets, {T} bars; folds={len(folds)}")

    rows = [_row("fixed-rule", "hard", fixed_rule_baseline(close, dates_ms))]

    POS_l, _, idx_l = train_eval.nested_walkforward(models.make_lstm, models.LSTM_GRID, X, fwd, folds,
                                                    warm=252, epochs=300)
    for band, tag in [(0.0, "none"), (0.3, "hard")]:
        rows.append(_row("LSTM-DMN", tag, train_eval.evaluate(POS_l, fwd, dates_ms, idx_l, band,
                         spread_bps=10.0, n_trials=len(models.LSTM_GRID), ppy=PPY)))

    POS_g, idx_g = gbt_model.gbt_positions(X, fwd, vol_nt, folds, warm=252)
    for band, tag in [(0.0, "none"), (0.3, "hard")]:
        rows.append(_row("GBT", tag, train_eval.evaluate(POS_g, fwd, dates_ms, idx_g, band,
                         spread_bps=10.0, n_trials=len(gbt_model.GBT_GRID), ppy=PPY)))

    print(f"\n{'model':<12}{'band':<6}{'netIR':>8}{'NW-t':>8}{'DSR':>8}{'+2022':>8}")
    print("-" * 50)
    for nm, bd, ir, t, dsr, y in rows:
        print(f"{nm:<12}{bd:<6}{ir:>8.2f}{t:>8.2f}{dsr:>8.2f}{y:>8}")

    Xall, yall = gbt_model._flatten(X, fwd, 252, T)
    gb = HistGradientBoostingRegressor(random_state=0, **gbt_model.GBT_GRID[0]).fit(Xall, yall)
    sub = np.random.default_rng(0).choice(len(Xall), size=min(20000, len(Xall)), replace=False)
    imp = permutation_importance(gb, Xall[sub], yall[sub], n_repeats=5, random_state=0)
    order = np.argsort(imp.importances_mean)[::-1]
    print("\n[feature importance] (permutation, higher = more used)")
    for i in order:
        print(f"  {FEAT_NAMES[i]:<10} {imp.importances_mean[i]:+.5f}")

    labels = [f"{nm}\n{bd}" for nm, bd, *_ in rows]
    irs = [r[2] for r in rows]
    palette = {"fixed-rule": "#64748b", "LSTM-DMN": "#2563eb", "GBT": "#16a34a"}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(labels, irs, color=[palette[r[0]] for r in rows])
    ax.axhline(0.92, ls="--", color="#2563eb", lw=1, label="LSTM 0.92")
    ax.axhline(1.11, ls="--", color="#64748b", lw=1, label="rule 1.11")
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_ylabel("net IR @10bps"); ax.set_title("GBT (tabular) vs LSTM vs rule (combined 18, OOS net)")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_gbt.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_gbt.png")


if __name__ == "__main__":
    main()
