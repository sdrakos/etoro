import paper1_RL.universe as U

def test_universe_is_fixed_and_deduped():
    assert 100 <= len(U.TICKERS) <= 200
    assert len(U.TICKERS) == len(set(U.TICKERS))         # no dupes
    assert all(isinstance(t, str) and t.isupper() for t in U.TICKERS)

def test_window_constants():
    assert U.START == "2015-01-01"
    assert U.END == "2024-12-31"

# Task 3: earnings-surprise drift matrix
import numpy as np
import paper1_RL.yahoo_research_data as Y

def test_surprise_matrix_t_plus_1_and_window():
    dates = np.arange(10)                                # 10 trading-day indices
    # ticker 0 ανακοινωνει στο index 2 με surprise +5%· ticker 1 ποτε
    ann = {0: [(2, 5.0)], 1: []}
    W = 3
    M = Y.surprise_matrix(dates, ann, n=2, window=W)
    # entry T+1: index 2 = nan (ημερα ανακοινωσης, δεν ξερουμε ακομα)
    assert np.isnan(M[2, 0])
    # drift window [3,4,5] = 5.0
    assert M[3, 0] == 5.0 and M[4, 0] == 5.0 and M[5, 0] == 5.0
    # εκτος window
    assert np.isnan(M[6, 0])
    # ticker χωρις earnings = ολο nan
    assert np.isnan(M[:, 1]).all()
