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


def test_robust_pick_prefers_2d_plateau_interior_over_edge_spike():
    # a 3x3 grid: a bright spike at a CORNER (few neighbours) vs a plateau whose INTERIOR
    # cell is surrounded by good neighbours. robust_pick must choose the interior, not the spike.
    rows = []
    for lb in (50, 100, 150):
        for bd in (0.0, 0.1, 0.2):
            ir = 1.0 if (lb in (100, 150) and bd in (0.1, 0.2)) else 0.0
            rows.append({"lookback": lb, "band": bd, "net_ir": ir})
    # plant a lone high spike at the (50, 0.0) corner
    rows[0]["net_ir"] = 5.0
    best = robustness.robust_pick(rows, knobs=["lookback", "band"], neighbor_span=1)
    assert best["net_ir"] >= 1.0           # not the isolated 5.0 spike's neighbourhood
    assert (best["lookback"], best["band"]) != (50, 0.0)   # never the corner spike
    assert best["lookback"] in (100, 150) and best["band"] in (0.1, 0.2)  # plateau interior
