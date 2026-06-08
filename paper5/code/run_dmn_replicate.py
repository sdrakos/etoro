#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-seed replication + attention attribution. Runs the 2x2+structured factorial
{LSTM, gated} x {no-pretrain, rwalk-pretrain, structured-pretrain} across 5 seeds on the REAL
combined-18 basket (hard band, net @10bps, PPY=252), and reports net IR mean+/-std plus mean |gate|.
Answers: (1) is the rwalk 1.28 robust? (2) does attention add anything, or is the lift pure LSTM
initialization (gated+rwalk ~= LSTM+rwalk and |gate|~=0)?"""
import sys, os
import numpy as np
import warnings; warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "paper4", "code"))
import metrics  # noqa: F401
import combined_data, crypto_features, train_eval, models, synth_data

FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
PPY = 252
SEEDS = [0, 1, 2, 3, 4]
CONDS = [
    ("LSTM noPT",    models.make_lstm,         models.LSTM_GRID[0],  None),
    ("LSTM rwalk",   models.make_lstm,         models.LSTM_GRID[0],  "randomwalk"),
    ("LSTM struct",  models.make_lstm,         models.LSTM_GRID[0],  "structured"),
    ("gated noPT",   models.make_gated_hybrid, models.GATED_GRID[0], None),
    ("gated rwalk",  models.make_gated_hybrid, models.GATED_GRID[0], "randomwalk"),
    ("gated struct", models.make_gated_hybrid, models.GATED_GRID[0], "structured"),
]


def main():
    close = combined_data.fetch_combined_daily()
    X, fwd, dates_ms = crypto_features.build(close)
    T = X.shape[1]
    folds = train_eval.make_folds(T, warm=252, first_train=1500, step=252)
    print(f"[data] {close.shape[1]} real assets, {T} bars; folds={len(folds)}; seeds={SEEDS}")

    rows = []
    for name, mk, cfg, kind in CONDS:
        irs, gates = [], []
        for s in SEEDS:
            train_eval.set_seed(s)
            if kind is None:
                trainer = None
            else:
                Xsyn, fsyn, _ = crypto_features.build(synth_data.make_synthetic(kind, 18, 6000, seed=s))
                state = train_eval.pretrain_model(mk, cfg, Xsyn, fsyn, epochs=300)
                trainer = train_eval.make_pretrained_trainer(state)
            train_eval.GATE_LOG.clear()
            POS, _, test_idx = train_eval.nested_walkforward(
                mk, [cfg], X, fwd, folds, warm=252, epochs=300, trainer=trainer)
            r = train_eval.evaluate(POS, fwd, dates_ms, test_idx, 0.3,
                                    spread_bps=10.0, n_trials=1, ppy=PPY)
            irs.append(r["net_ir"])
            g = float(np.mean(train_eval.GATE_LOG)) if train_eval.GATE_LOG else None
            if g is not None:
                gates.append(g)
            print(f"  {name:<13} seed{s}: IR {r['net_ir']:+.2f}" + (f"  |g| {g:.3f}" if g is not None else ""))
        rows.append((name, irs, gates))

    print(f"\n{'condition':<14}{'netIR mean':>12}{'std':>8}{'mean|gate|':>12}")
    print("-" * 46)
    for name, irs, gates in rows:
        gm = f"{np.mean(gates):.3f}" if gates else "-"
        print(f"{name:<14}{np.mean(irs):>12.2f}{np.std(irs):>8.2f}{gm:>12}")

    def col(n):
        return next(irs for nm, irs, _ in rows if nm == n)
    lstm_rw, gated_rw = col("LSTM rwalk"), col("gated rwalk")
    print(f"\n[attention] gated+rwalk {np.mean(gated_rw):.2f}+/-{np.std(gated_rw):.2f}  vs  "
          f"LSTM+rwalk {np.mean(lstm_rw):.2f}+/-{np.std(lstm_rw):.2f}  "
          f"-> diff {np.mean(gated_rw) - np.mean(lstm_rw):+.2f}")

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, (name, irs, _g) in enumerate(rows):
        ax.scatter([i] * len(irs), irs, s=28, color="#64748b", zorder=3)
        ax.scatter([i], [np.mean(irs)], s=120, marker="_", color="#dc2626", zorder=4)
    ax.axhline(0.92, ls="--", color="#2563eb", lw=1, label="LSTM ref 0.92")
    ax.axhline(0.0, color="#000", lw=0.6)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows], rotation=30, ha="right")
    ax.set_ylabel("net IR @10bps (hard band)")
    ax.set_title("Multi-seed replication (5 seeds): pretraining + attention attribution")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_dmn_replicate.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_dmn_replicate.png")


if __name__ == "__main__":
    main()
