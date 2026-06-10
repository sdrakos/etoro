import numpy as np
import sizing_dial


def test_presets_increase_target_vol_monotonically():
    p = sizing_dial.PRESETS
    assert p["conservative"]["target_vol"] < p["balanced"]["target_vol"] < p["aggressive"]["target_vol"]


def test_eur_path_compounds_from_start_capital():
    net = np.array([0.10, -0.05, 0.20])
    end = sizing_dial.eur_end_value(net, start=10_000.0)
    expected = 10_000.0 * 1.10 * 0.95 * 1.20
    assert np.isclose(end, expected)


def test_realized_maxdd_scales_with_target_vol():
    # doubling target_vol roughly doubles realized vol of the position book (linear dial)
    rng = np.random.default_rng(0)
    sig = rng.standard_normal(1000) * 0.01
    lo = sizing_dial.realized_vol_of(sig * 1.0)
    hi = sizing_dial.realized_vol_of(sig * 2.0)
    assert 1.8 <= hi / lo <= 2.2
