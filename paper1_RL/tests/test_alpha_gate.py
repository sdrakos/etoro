# paper1_RL/tests/test_alpha_gate.py
import numpy as np
import paper1_RL.alpha_gate as G

def test_gate_detects_planted_signal(planted):
    res = G.evaluate(signal=planted["score"], close=planted["close"], hold=1)
    assert res["IC"] > 0.05
    assert res["IC_t"] > 2          # περναει το gate
    assert G.passes(res)

def test_gate_rejects_noise(noise_only):
    res = G.evaluate(signal=noise_only["score"], close=noise_only["close"], hold=1)
    assert abs(res["IC_t"]) < 2     # κοβεται απο το gate
    assert not G.passes(res)
