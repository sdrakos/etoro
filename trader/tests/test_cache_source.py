from trader.data.cache import Cache


def test_two_sources_same_bar_do_not_collide(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    ts = 1_700_000_000_000
    cache.upsert([{"ticker": "AAPL", "timestamp": ts,
                   "open": 1, "high": 1, "low": 1, "close": 100.0,
                   "volume": 1, "vwap": 1}], source="massive")
    cache.upsert([{"ticker": "AAPL", "timestamp": ts,
                   "open": 1, "high": 1, "low": 1, "close": 200.0,
                   "volume": 1, "vwap": 1}], source="yahoo")

    m = cache.query("AAPL", 0, ts + 1, source="massive")
    y = cache.query("AAPL", 0, ts + 1, source="yahoo")
    assert len(m) == 1 and m.iloc[0]["close"] == 100.0
    assert len(y) == 1 and y.iloc[0]["close"] == 200.0


def test_coverage_is_per_source(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert([{"ticker": "AAPL", "timestamp": 1_700_000_000_000,
                   "open": 1, "high": 1, "low": 1, "close": 1,
                   "volume": 1, "vwap": 1}], source="yahoo")
    assert cache.coverage("AAPL", source="massive") is None
    assert cache.coverage("AAPL", source="yahoo") is not None
