"""Axis 3 driver: compare the fixed 5-asset basket vs ENB-greedy 3/5/7 over an extended pool.
Net-of-cost, leak-free. Prints IR/maxDD/ENB per basket."""
from __future__ import annotations
import numpy as np

import basket
import data
import eval as ev
import rule

POOL = ("SPY", "TLT", "GLD", "BTC-USD", "UUP", "QQQ", "EEM", "HYG", "SLV")
BASE = {"lookback": 252, "target_vol": 0.15, "smooth_span": 5, "band": 0.15}


def _score(close):
    fwd = ev.forward_returns(close)
    spreads = [data.SPREADS_BPS.get(t, 5.0) for t in close.columns]
    rows = np.arange(252, len(close) - 1)
    pos = rule.positions(close, lookback=BASE["lookback"], target_vol=BASE["target_vol"],
                         smooth_span=BASE["smooth_span"])
    m = ev.evaluate(pos, fwd, rows, spreads, band=BASE["band"])
    enb = basket.effective_bets(close.pct_change().to_numpy()[1:])
    return m, enb


def main():
    full = data.load_basket(tickers=POOL)
    ret = full.pct_change().to_numpy()[1:]
    print(f"{'basket':28} {'enb':>5} {'net_ir':>8} {'max_dd':>8}")
    # fixed 5-asset
    five = data.load_basket(tickers=data.SWEET_SPOT)
    m, enb = _score(five); print(f"{'fixed-5 (sweet spot)':28} {enb:5.1f} {m['net_ir']:8.2f} {m['max_dd']:8.2%}")
    for k in (3, 5, 7):
        names = basket.greedy_enb(ret, list(full.columns), k=k)
        sub = data.load_basket(tickers=tuple(names))
        m, enb = _score(sub)
        print(f"{'enb-greedy-' + str(k) + ' ' + '/'.join(names):28.28} {enb:5.1f} {m['net_ir']:8.2f} {m['max_dd']:8.2%}")


if __name__ == "__main__":
    main()
