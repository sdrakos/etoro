"""Probe: the rule on the 4-asset basket WITHOUT BTC (SPY/TLT/GLD/UUP) over the deep
2007-2026 window. This tests 2008-crisis durability that the BTC-limited 5-asset sweet
spot cannot reach (BTC history starts ~2014). Same locked base config, net-of-cost, leak-free."""
from __future__ import annotations
import numpy as np

import basket
import data
import eval as ev
import overlays
import rule

import _paths  # noqa: F401
import band_eval   # paper5/code
import metrics     # paper4/code


def _crisis_irs(net, yr):
    """net IR for the three crisis years, given the per-period net stream and its year labels."""
    out = {}
    for y in (2008, 2020, 2022):
        rr = net[(yr == y) & np.isfinite(net)]
        out[y] = metrics.ann_ir(rr, 252) if len(rr) > 20 else float("nan")
    return out

BASKET = ("SPY", "TLT", "GLD", "UUP")               # no BTC -> deep 2007 history
BASE = {"lookback": 252, "target_vol": 0.15, "smooth_span": 5, "band": 0.15}
PRESETS = {"conservative": 0.10, "balanced": 0.15, "aggressive": 0.20}


def main():
    close = data.load_basket(tickers=BASKET)
    T, N = close.shape
    print(f"window {close.index[0].date()}..{close.index[-1].date()}  rows={T}  assets={list(close.columns)}")
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS[t] for t in close.columns]
    rows = np.arange(252, T - 1)
    years = close.index.year.to_numpy()

    enb = basket.effective_bets(close.pct_change().to_numpy()[1:])
    print(f"ENB = {enb:.2f} / {N}")

    pos = rule.positions(close, lookback=BASE["lookback"], target_vol=BASE["target_vol"],
                         smooth_span=BASE["smooth_span"])
    m = ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])
    print(f"base: net_ir={m['net_ir']:.2f}  nw_t={m['nw_t']:.2f}  dsr={m['dsr']:.2f}  "
          f"maxDD={m['max_dd']:.1%}  ann={m['ann']:.1%}  n={m['n']}")

    W = band_eval.apply_band(pos, BASE["band"])[rows] / N
    net = ev._net_with_per_asset_spreads(W, fwd[rows], spreads)
    yr = years[rows]
    print("durability by year (net IR), crises flagged:")
    for y in range(int(yr.min()), int(yr.max()) + 1):
        rr = net[(yr == y) & np.isfinite(net)]
        if len(rr) > 20:
            ir = metrics.ann_ir(rr, 252)
            flag = "  <-- crisis" if y in (2008, 2020, 2022) else ""
            print(f"   {y}: {ir:+.2f}{flag}")

    print("sizing presets (EUR on 10k):")
    for name, tv in PRESETS.items():
        p = rule.positions(close, lookback=BASE["lookback"], target_vol=tv, smooth_span=BASE["smooth_span"])
        mm = ev.evaluate(p, fwd, rows, spreads, band=BASE["band"])
        Wp = band_eval.apply_band(p, BASE["band"])[rows] / N
        netp = ev._net_with_per_asset_spreads(Wp, fwd[rows], spreads)
        eur = 10000.0 * float(np.prod(1.0 + netp[np.isfinite(netp)]))
        print(f"   {name:12} tv={tv:.2f}  net_ir={mm['net_ir']:.2f}  maxDD={mm['max_dd']:.1%}  EUR={eur:.0f}")

    # ---- overlay ablation on this deeper-drawdown / 2008-inclusive basket ----
    print("overlay ablation (vs base; gate = maxDD cut >=20% AND net-IR not down >0.1):")
    pr_full = ev._net_with_per_asset_spreads(band_eval.apply_band(pos, BASE["band"]) / N, fwd, spreads)
    pr_full = np.nan_to_num(pr_full, nan=0.0)
    vix = data.load_vix().reindex(close.index).ffill().to_numpy()
    dd_mask = overlays.drawdown_control(pos, pr_full, dd_limit=0.10)
    vix_mask = overlays.vix_gate(pos, vix, threshold=30.0)
    bo_mask = overlays.bocpd_brake(pos, close)
    variants = {"base": pos, "+drawdown": pos * dd_mask, "+vix": pos * vix_mask,
                "+bocpd": pos * bo_mask, "+all": pos * dd_mask * vix_mask * bo_mask}
    base_m = ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])
    yr = years[rows]
    print(f"   {'variant':11} {'net_ir':>7} {'maxDD':>7}  {'2008':>6} {'2020':>6} {'2022':>6}  verdict")
    for name, pv in variants.items():
        mm = ev.evaluate(pv, fwd, rows, spreads, band=BASE["band"])
        nv = ev._net_with_per_asset_spreads(band_eval.apply_band(pv, BASE["band"])[rows] / N, fwd[rows], spreads)
        cr = _crisis_irs(nv, yr)
        if name == "base":
            verdict = "-"
        else:
            dd_cut = (abs(base_m["max_dd"]) - abs(mm["max_dd"])) / (abs(base_m["max_dd"]) + 1e-9)
            verdict = "PASS" if (dd_cut >= 0.20 and mm["net_ir"] >= base_m["net_ir"] - 0.1) else "NULL"
        print(f"   {name:11} {mm['net_ir']:7.2f} {mm['max_dd']:7.1%}  "
              f"{cr[2008]:+6.2f} {cr[2020]:+6.2f} {cr[2022]:+6.2f}  {verdict}")


if __name__ == "__main__":
    main()
