import os, sys, tempfile
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import crypto_data


def test_basket_is_eight_unique():
    assert len(crypto_data.BASKET) == 8
    assert len(set(crypto_data.BASKET)) == 8
    assert "BTC-USD" in crypto_data.BASKET


def test_cache_roundtrip_preserves_frame():
    idx = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    df = pd.DataFrame({"BTC-USD": [1.0, 2.0, 3.0], "ETH-USD": [4.0, 5.0, 6.0]}, index=idx)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.npz")
        crypto_data.save_cache(p, df)
        out = crypto_data.load_cache(p)
    pd.testing.assert_frame_equal(out, df)
