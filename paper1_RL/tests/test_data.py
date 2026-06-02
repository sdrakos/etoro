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

def test_announcement_index_maps_and_filters_out_of_window():
    all_ts = [100, 200, 300, 400]                        # sorted trading-day timestamps
    assert Y.announcement_index(all_ts, 250) == 1        # nearest <= 250 is index 1 (200)
    assert Y.announcement_index(all_ts, 300) == 2        # exact match
    assert Y.announcement_index(all_ts, 450) is None     # future (beyond last) -> NOT clamped to 3
    assert Y.announcement_index(all_ts, 50) is None      # before first -> dropped
    assert Y.announcement_index([], 100) is None

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

# Task 4: cache-aside load_universe
def test_load_universe_caches(tmp_path, monkeypatch):
    calls = {"n": 0}
    def fake_fetch():
        calls["n"] += 1
        T, N = 5, 3
        return dict(close=np.ones((T, N)), vol=np.ones((T, N)),
                    dates=np.arange(T), tickers=["A","B","C"],
                    earnings={0: [], 1: [], 2: []},
                    sector={"A":"Tech","B":"Tech","C":"Energy"},
                    vix=np.ones(T))
    monkeypatch.setattr(Y, "_fetch_all", fake_fetch)
    cache = tmp_path / "u.npz"
    d1 = Y.load_universe(cache_path=str(cache))           # miss -> fetch
    d2 = Y.load_universe(cache_path=str(cache))           # hit  -> no fetch
    assert calls["n"] == 1
    assert d2["close"].shape == (5, 3)
    assert list(d2["tickers"]) == ["A","B","C"]
