import numpy as np
import overlays


def test_drawdown_control_cuts_exposure_after_loss():
    # a book that loses for a while should have exposure cut to < 1 during the drawdown
    pos = np.ones((100, 1))
    port_ret = np.where(np.arange(100) < 50, -0.01, 0.01)   # lose then recover
    mask = overlays.drawdown_control(pos, port_ret, dd_limit=0.05)
    assert mask.shape == (100, 1)
    assert np.all(mask <= 1.0 + 1e-9) and np.all(mask >= 0.0)
    assert mask[40, 0] < 1.0          # deep in the drawdown -> exposure reduced
    assert mask[0, 0] == 1.0          # no drawdown yet at t=0 -> full exposure


def test_vix_gate_derisks_when_vix_high():
    pos = np.ones((6, 1))
    vix = np.array([15, 15, 40, 40, 15, 15], float)         # spike in the middle
    mask = overlays.vix_gate(pos, vix, threshold=30.0)
    assert mask[2, 0] == 0.0 and mask[3, 0] == 0.0          # gated off during spike
    assert mask[0, 0] == 1.0


def test_overlay_is_causal_no_lookahead():
    # changing a FUTURE return must not change the mask at an earlier time
    pos = np.ones((20, 1))
    r1 = np.full(20, 0.01); r2 = r1.copy(); r2[15] = -0.5
    m1 = overlays.drawdown_control(pos, r1, dd_limit=0.05)
    m2 = overlays.drawdown_control(pos, r2, dd_limit=0.05)
    assert np.allclose(m1[:15], m2[:15])                    # past unaffected by future
