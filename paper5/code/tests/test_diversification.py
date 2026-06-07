import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import diversification_check as dc


def test_enb_identity_is_n():
    # fully uncorrelated -> ENB == N
    assert abs(dc.effective_bets(np.eye(5)) - 5.0) < 1e-6


def test_enb_all_identical_is_one():
    # perfectly correlated block -> ENB -> 1
    corr = np.ones((4, 4))
    assert abs(dc.effective_bets(corr) - 1.0) < 1e-6


def test_avg_abs_offdiag_ignores_diagonal():
    corr = np.array([[1.0, 0.5], [0.5, 1.0]])
    assert abs(dc.avg_abs_offdiag(corr) - 0.5) < 1e-9
