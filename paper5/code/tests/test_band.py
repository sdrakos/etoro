import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import band_eval


def test_band_blocks_small_moves_one_switch_not_four():
    # one asset, start flat, then target jumps; band 0.3 from a held +0.5
    # targets: .5(set), .6, .7, .85, .8  -> from 0: first sets .5 (|.5-0|>.3),
    # then .6/.7 blocked from .5, .85 switches (|.85-.5|=.35>.3), .8 blocked.
    pos = np.array([[0.5], [0.6], [0.7], [0.85], [0.8]])
    held = band_eval.apply_band(pos, 0.3)
    assert held[:, 0].tolist() == [0.5, 0.5, 0.5, 0.85, 0.85]
    # number of actual switches (changes) = 2 (0->.5, .5->.85)
    switches = int((np.abs(np.diff(held[:, 0])) > 1e-12).sum()) + 1  # +1 for the initial set
    assert switches == 2


def test_band_zero_is_identity():
    pos = np.array([[0.1], [-0.2], [0.4], [0.4]])
    held = band_eval.apply_band(pos, 0.0)
    assert np.allclose(held, pos)
