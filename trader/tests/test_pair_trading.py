"""Synthetic-series tests for pair_trading math helpers."""
import numpy as np
import pandas as pd
import pytest

from trader.strategies.pair_trading import (
    PairTradingStrategy,
    PairParams,
    compute_hedge_ratio,
    compute_zscore,
    cointegration_pvalue,
)


def _cointegrated_pair(n: int = 300, beta: float = 2.0, seed: int = 42):
    rng = np.random.default_rng(seed)
    amd = np.cumsum(rng.normal(0, 1, n)) + 100
    noise = rng.normal(0, 0.5, n)
    nvda = beta * amd + 10 + noise
    return pd.Series(amd, name="AMD"), pd.Series(nvda, name="NVDA")


def test_hedge_ratio_recovers_known_beta():
    amd, nvda = _cointegrated_pair(beta=2.0)
    beta = compute_hedge_ratio(nvda.tail(120), amd.tail(120))
    assert 1.85 < beta < 2.15


def test_cointegration_pvalue_low_for_cointegrated():
    amd, nvda = _cointegrated_pair()
    spread = nvda - 2.0 * amd
    p = cointegration_pvalue(spread.tail(120).to_numpy())
    assert p < 0.05


def test_cointegration_pvalue_high_for_random_walks():
    rng = np.random.default_rng(7)
    a = pd.Series(np.cumsum(rng.normal(0, 1, 300)))
    b = pd.Series(np.cumsum(rng.normal(0, 1, 300)))
    spread = b - 1.0 * a
    p = cointegration_pvalue(spread.tail(120).to_numpy())
    assert p > 0.05
