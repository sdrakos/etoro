import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import synth_data
import diversification_check as dc


def test_shape_and_finite_positive():
    df = synth_data.make_synthetic("structured", n_assets=18, T=1500, seed=0)
    assert df.shape == (1500, 18)
    assert np.isfinite(df.to_numpy()).all()
    assert (df.to_numpy() > 0).all()


def test_series_are_uncorrelated_high_enb():
    df = synth_data.make_synthetic("structured", n_assets=18, T=1500, seed=0)
    _corr, avg, enb = dc.basket_stats(df)
    assert avg < 0.15
    assert enb > 12.0


def test_determinism_and_kind_differs():
    a = synth_data.make_synthetic("structured", n_assets=4, T=500, seed=1)
    b = synth_data.make_synthetic("structured", n_assets=4, T=500, seed=1)
    assert np.allclose(a.to_numpy(), b.to_numpy())
    c = synth_data.make_synthetic("randomwalk", n_assets=4, T=500, seed=1)
    assert not np.allclose(a.to_numpy(), c.to_numpy())
