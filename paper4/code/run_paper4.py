"""Produce paper4's headline results: TSMOM vs cpd_momentum vs belief_gated, net of costs."""
from __future__ import annotations
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data import load_close_matrix
from harness import run_variant
from metrics import durability_by_year

FIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))


def _ffill(close):
    out = close.copy()
    for j in range(out.shape[1]):
        col = out[:, j]
        last = np.nan
        for i in range(len(col)):
            if np.isnan(col[i]):
                col[i] = last
            else:
                last = col[i]
    return out


def main():
    close, dates, tickers = load_close_matrix()
    close = _ffill(close)
    print(f"universe: {len(tickers)} tickers, {close.shape[0]} days")
    results = {}
    plt.figure(figsize=(10, 6))
    for variant in ("tsmom", "cpd_momentum", "belief_gated"):
        res = run_variant(variant, close, k=10, warmup=252, embargo=21,
                          spread_bps=5.0, short_fin_bps_annual=300.0, n_trials=3)
        net = res["net"][252:len(res["net"]) - 21]
        dts = dates[252:len(res["net"]) - 21]
        dur = durability_by_year(net, dts)
        results[variant] = {"ir": res["ir"], "nw_t": res["nw_t"], "dsr": res["dsr"],
                            "max_dd": res["max_dd"], "turnover": res["turnover"],
                            "durability": dur}
        plt.plot(np.cumprod(1 + net), label=f"{variant} (IR={res['ir']:.2f})")
        print(f"{variant:<14} IR={res['ir']:+.2f}  NW-t={res['nw_t']:+.2f}  "
              f"DSR={res['dsr']:.2f}  maxDD={res['max_dd']*100:+.1f}%  turn={res['turnover']:.3f}")
    plt.legend(); plt.title("paper4: cumulative net-of-cost equity"); plt.grid(alpha=0.3)
    os.makedirs(FIG, exist_ok=True)
    plt.savefig(os.path.join(FIG, "equity_variants.png"), dpi=120)
    with open(os.path.join(FIG, "..", "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved figures/equity_variants.png and results.json")


if __name__ == "__main__":
    main()
