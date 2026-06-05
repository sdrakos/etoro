import numpy as np
from bocpd import bocpd_gaussian


def test_detects_mean_shift():
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0, 1, 150), rng.normal(4, 1, 150)])
    sev = bocpd_gaussian(x, hazard=1/100, sigma2=1.0)
    assert sev[150:165].max() > 0.3        # spikes shortly after the shift
    assert sev[40:140].max() < 0.25        # quiet in the stable segment


def test_quiet_on_stationary():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 400)
    sev = bocpd_gaussian(x, hazard=1/250, sigma2=1.0)
    assert sev.mean() < 0.1


def test_severity_in_unit_interval_and_length():
    sev = bocpd_gaussian(np.zeros(30), hazard=1/50, sigma2=1.0)
    assert sev.shape == (30,)
    assert (sev >= 0).all() and (sev <= 1).all()
