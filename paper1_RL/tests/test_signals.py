# paper1_RL/tests/test_signals.py
import numpy as np
import paper1_RL.signals as S

def test_zscore_cross_section():
    x = np.array([1.0, 2.0, 3.0])
    z = S.zscore_xs(x)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std() - 1.0) < 1e-6

def test_sector_neutral_demeans_within_group():
    score = np.array([1.0, 3.0, 10.0, 20.0])             # 2 sectors
    sectors = np.array(["A", "A", "B", "B"])
    out = S.sector_neutral(score, sectors)
    # καθε sector εχει mean 0 μετα
    assert abs(out[:2].mean()) < 1e-9
    assert abs(out[2:].mean()) < 1e-9

def test_vix_theta_scale_derisks_when_vix_high():
    w = np.array([1.0, -1.0])
    lo = S.vix_theta_scale(w, vix_now=12.0, vix_ref=20.0)   # ηρεμια -> πιο γεματο
    hi = S.vix_theta_scale(w, vix_now=40.0, vix_ref=20.0)   # stress -> de-risk
    assert np.abs(hi).sum() < np.abs(lo).sum()

def test_pead_signal_uses_surprise_matrix():
    # surprise matrix με 1 ενεργη μερα
    M = np.full((3, 2), np.nan); M[1, 0] = 5.0
    s = S.pead_signal_at(M, t=1)
    assert s[0] == 5.0 and np.isnan(s[1])
