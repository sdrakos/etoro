import os, sys
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "code")))
from signal_engine import target_weights, train_full


def _fake_fetch(seed=0, T=400, N=4):
    rng = np.random.default_rng(seed)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100
    return close, ["SPY", "TLT", "GLD", "DBC"]


def test_rules_weights_keys_and_gross():
    w = target_weights("rules", fetch_close=lambda: _fake_fetch())
    assert set(w) <= {"SPY", "TLT", "GLD", "DBC"}
    assert sum(abs(v) for v in w.values()) <= 1.0 + 1e-9


def test_rules_is_deterministic():
    w1 = target_weights("rules", fetch_close=lambda: _fake_fetch(0))
    w2 = target_weights("rules", fetch_close=lambda: _fake_fetch(0))
    assert w1 == w2


def test_train_full_then_ml_signal(tmp_path):
    close, tickers = _fake_fetch(T=600, N=4)
    train_full(close, tickers, name="t", root=str(tmp_path), epochs=20)
    w = target_weights("ml", fetch_close=lambda: (close, tickers), model_name="t",
                       model_root=str(tmp_path))
    assert set(w) <= set(tickers)
    assert all(-1.0 <= v <= 1.0 for v in w.values())
