"""Axis 2 driver: ablate each overlay vs the base config on the real basket. Print the
ablation table and the PASS/NULL verdict per the pre-registered gate. Net-of-cost, leak-free."""
from __future__ import annotations
import numpy as np

import data
import eval as ev
import overlays
import rule

# Axis-1 locked base config
BASE = {"lookback": 252, "vol_window": 30, "target_vol": 0.15, "smooth_span": 5, "band": 0.15}


def _port_ret(pos, fwd, band, N):
    import band_eval, costs  # via eval's _paths
    W = band_eval.apply_band(pos, band) / N
    return costs.net_returns(W, np.nan_to_num(np.asarray(fwd), nan=0.0), 0.0, 0.0)


def main():
    close = data.load_basket()
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS[t] for t in close.columns]
    T, N = close.shape
    rows = np.arange(252, T - 1)
    base_pos = rule.positions(close, lookback=BASE["lookback"], vol_window=BASE["vol_window"],
                              target_vol=BASE["target_vol"], smooth_span=BASE["smooth_span"])

    def metr(pos):
        return ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])

    base = metr(base_pos)
    pr = _port_ret(base_pos, fwd, BASE["band"], N)
    variants = {
        "base": base_pos,
        "+drawdown": base_pos * overlays.drawdown_control(base_pos, pr, dd_limit=0.10),
        "+vix": base_pos * overlays.vix_gate(base_pos, data.load_vix().reindex(close.index).ffill().to_numpy(), 30.0),
        "+bocpd": base_pos * overlays.bocpd_brake(base_pos, close),
    }
    print(f"{'variant':12} {'net_ir':>8} {'max_dd':>8} {'verdict':>8}")
    for name, pos in variants.items():
        m = metr(pos)
        if name == "base":
            verdict = "-"
        else:
            # pre-registered: maxDD cut >=20% AND net_ir not down by >0.1
            dd_cut = (abs(base["max_dd"]) - abs(m["max_dd"])) / (abs(base["max_dd"]) + 1e-9)
            verdict = "PASS" if (dd_cut >= 0.20 and m["net_ir"] >= base["net_ir"] - 0.1) else "NULL"
        print(f"{name:12} {m['net_ir']:8.2f} {m['max_dd']:8.2%} {verdict:>8}")


if __name__ == "__main__":
    main()
