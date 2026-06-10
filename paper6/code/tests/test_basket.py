import numpy as np
import basket


def test_enb_of_independent_assets_equals_count():
    # uncorrelated columns -> ENB ~= N
    rng = np.random.default_rng(0)
    R = rng.standard_normal((2000, 4))
    enb = basket.effective_bets(R)
    assert 3.5 <= enb <= 4.0


def test_enb_of_redundant_assets_is_small():
    # all columns identical -> ENB ~= 1
    rng = np.random.default_rng(1)
    base = rng.standard_normal((2000, 1))
    R = np.repeat(base, 4, axis=1)
    enb = basket.effective_bets(R)
    assert enb < 1.2


def test_greedy_select_prefers_uncorrelated():
    rng = np.random.default_rng(2)
    a = rng.standard_normal(2000)
    R = np.column_stack([a, a * 0.99 + 0.01 * rng.standard_normal(2000),  # redundant with a
                         rng.standard_normal(2000), rng.standard_normal(2000)])  # independent
    names = ["a", "a2", "b", "c"]
    chosen = basket.greedy_enb(R, names, k=3)
    assert "a2" not in chosen          # the redundant twin is dropped
    assert len(chosen) == 3
