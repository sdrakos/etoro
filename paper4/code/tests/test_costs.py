import numpy as np
from costs import net_returns


def test_no_turnover_no_short_equals_gross():
    w = np.array([[0.5, 0.5], [0.5, 0.5]])
    fwd = np.array([[0.01, 0.02], [0.0, 0.0]])
    net = net_returns(w, fwd, spread_bps=10.0, short_fin_bps_annual=300.0)
    # row 0 charges initial turnover (1.0); row 1 has no turnover, no shorts
    assert np.isclose(net[1], 0.0)


def test_short_financing_charged():
    w = np.array([[0.5, -0.5]])
    fwd = np.array([[0.0, 0.0]])
    net = net_returns(w, fwd, spread_bps=0.0, short_fin_bps_annual=2520.0)  # 0.01/day on 1bp basis
    # short notional 0.5 -> daily fin = (2520/1e4/252)*0.5 = 0.001*0.5 = 5e-4
    assert np.isclose(net[0], -5e-4)


def test_turnover_charged_on_rebalance():
    w = np.array([[0.0, 0.0], [1.0, -1.0]])
    fwd = np.array([[0.0, 0.0], [0.0, 0.0]])
    net = net_returns(w, fwd, spread_bps=10.0, short_fin_bps_annual=0.0)
    # row1 turnover = |1-0|+|-1-0| = 2.0 ; cost = 10/1e4 * 2 = 0.002
    assert np.isclose(net[1], -0.002)
