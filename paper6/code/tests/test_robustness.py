import numpy as np
import robustness


def test_grid_sweep_returns_one_row_per_combo():
    grid = {"lookback": [60, 120], "band": [0.0, 0.1], "target_vol": [0.15], "smooth_span": [5]}
    # fake scorer: IR = lookback/1000 - band (deterministic, monotone)
    def score(lookback, band, target_vol, smooth_span):
        return lookback / 1000.0 - band
    rows = robustness.sweep(grid, score)
    assert len(rows) == 2 * 2 * 1 * 1
    assert {"lookback", "band", "target_vol", "smooth_span", "net_ir"} <= set(rows[0])


def test_stable_center_prefers_plateau_over_spike():
    # one sharp spike (argmax) vs a broad plateau; center selector must avoid the spike
    rows = [
        {"lookback": 20, "band": 0.0, "target_vol": 0.15, "smooth_span": 5, "net_ir": 5.0},  # spike
        {"lookback": 100, "band": 0.1, "target_vol": 0.15, "smooth_span": 5, "net_ir": 1.0},
        {"lookback": 120, "band": 0.1, "target_vol": 0.15, "smooth_span": 5, "net_ir": 1.0},
        {"lookback": 140, "band": 0.1, "target_vol": 0.15, "smooth_span": 5, "net_ir": 1.0},
    ]
    best = robustness.stable_center(rows, key="lookback", neighbor_span=2)
    # the plateau center (120) wins, not the isolated spike (20)
    assert best["lookback"] == 120
