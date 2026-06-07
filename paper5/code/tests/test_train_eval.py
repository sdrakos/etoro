import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import train_eval, models


def test_make_folds_are_contiguous_and_after_first_train():
    folds = train_eval.make_folds(T=300, warm=20, first_train=100, step=50)
    assert folds[0][0] == 100
    # test spans tile contiguously: each test_hi equals the next train_hi
    for (a_lo, a_hi), (b_lo, b_hi) in zip(folds, folds[1:]):
        assert a_hi == b_lo
    assert folds[-1][1] <= 300


def test_nested_wf_fills_only_test_spans_and_evaluate_is_finite():
    rng = np.random.default_rng(0)
    N, T, F = 3, 220, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    dates_ms = (np.arange(T) * 86_400_000 + 1_500_000_000_000).astype("int64")
    folds = train_eval.make_folds(T, warm=20, first_train=120, step=50)
    POS, chosen, test_idx = train_eval.nested_walkforward(
        models.make_lstm, models.LSTM_GRID[:1], X, fwd, folds, warm=20, epochs=5)
    # train region (before first test) must be untouched zeros -> no leakage into past
    assert np.allclose(POS[:, :120], 0.0)
    assert test_idx.min() == 120
    res = train_eval.evaluate(POS, fwd, dates_ms, test_idx, band=0.3,
                              spread_bps=10.0, n_trials=1)
    for k in ("net_ir", "nw_t", "dsr", "n"):
        assert np.isfinite(res[k])
