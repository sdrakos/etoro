import paper1_RL.universe as U

def test_universe_is_fixed_and_deduped():
    assert 100 <= len(U.TICKERS) <= 200
    assert len(U.TICKERS) == len(set(U.TICKERS))         # no dupes
    assert all(isinstance(t, str) and t.isupper() for t in U.TICKERS)

def test_window_constants():
    assert U.START == "2015-01-01"
    assert U.END == "2024-12-31"
