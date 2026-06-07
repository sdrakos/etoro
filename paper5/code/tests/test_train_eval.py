import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import train_eval, models


def test_warmup_lambda_ramps_then_constant():
    vals = [train_eval.warmup_lambda(s, 10) for s in range(15)]
    assert vals[0] < 1.0
    assert all(b >= a for a, b in zip(vals, vals[1:]))   # non-decreasing
    assert abs(vals[9] - 1.0) < 1e-9                     # reached 1 by step 10 (index 9)
    assert all(abs(v - 1.0) < 1e-9 for v in vals[10:])   # constant after


def test_warmup_lambda_zero_is_constant_one():
    assert all(abs(train_eval.warmup_lambda(s, 0) - 1.0) < 1e-9 for s in range(5))


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


def test_set_requires_grad_freezes_correctly():
    net = models.make_gated_hybrid(10, models.GATED_GRID[0])
    train_eval._set_requires_grad(net, lstm=True, attn=False)
    assert all(p.requires_grad for p in net.lstm.parameters())
    assert all(not p.requires_grad for p in net.enc.parameters())
    assert net.gate.requires_grad is False
    train_eval._set_requires_grad(net, lstm=False, attn=True)
    assert all(not p.requires_grad for p in net.lstm.parameters())
    assert all(p.requires_grad for p in net.enc.parameters())
    assert net.gate.requires_grad is True


def test_two_stage_trainer_returns_finite_and_right_shape():
    import torch
    rng = np.random.default_rng(0)
    N, T, F = 3, 120, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    net, mu, sd, best = train_eval._train_fold_two_stage(
        models.make_gated_hybrid, X, fwd, 0, T, models.GATED_GRID[0], epochs=6)
    assert np.isfinite(best)
    with torch.no_grad():
        out = net((torch.tensor(X[:, :20], dtype=torch.float32) - mu) / sd)
    assert out.shape == (3, 20)


def test_nested_wf_accepts_two_stage_trainer():
    rng = np.random.default_rng(0)
    N, T, F = 3, 160, 10
    X = rng.standard_normal((N, T, F)).astype("float32")
    fwd = rng.standard_normal((N, T)).astype("float32") * 0.01
    folds = train_eval.make_folds(T, warm=20, first_train=100, step=40)
    POS, chosen, idx = train_eval.nested_walkforward(
        models.make_gated_hybrid, models.GATED_GRID[:1], X, fwd, folds,
        warm=20, epochs=4, trainer=train_eval._train_fold_two_stage)
    assert np.allclose(POS[:, :100], 0.0)
    assert idx.min() == 100


def test_pretrain_model_returns_loadable_state():
    rng = np.random.default_rng(0)
    N, T, F = 4, 120, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    m = models.make_gated_hybrid(F, models.GATED_GRID[0])
    m.load_state_dict(state)


def test_pretrained_trainer_resets_gate_to_zero():
    rng = np.random.default_rng(0)
    N, T, F = 3, 80, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    trainer = train_eval.make_pretrained_trainer(state)
    net, mu, sd, best = trainer(models.make_gated_hybrid, Xs, fs, 0, T, models.GATED_GRID[0], epochs=0)
    assert float(net.gate) == 0.0


def test_pretrained_trainer_finetunes_finite():
    import torch
    rng = np.random.default_rng(0)
    N, T, F = 3, 120, 10
    Xs = rng.standard_normal((N, T, F)).astype("float32")
    fs = rng.standard_normal((N, T)).astype("float32") * 0.01
    state = train_eval.pretrain_model(models.make_gated_hybrid, models.GATED_GRID[0], Xs, fs, epochs=4)
    trainer = train_eval.make_pretrained_trainer(state)
    net, mu, sd, best = trainer(models.make_gated_hybrid, Xs, fs, 0, T, models.GATED_GRID[0], epochs=6)
    assert np.isfinite(best)
    with torch.no_grad():
        out = net((torch.tensor(Xs[:, :20], dtype=torch.float32) - mu) / sd)
    assert out.shape == (3, 20)
