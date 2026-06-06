from instrument_map import resolve, renormalize


def _fake_search(found):
    def search(ticker):
        return found.get(ticker)
    return search


def test_resolve_maps_found_skips_missing():
    search = _fake_search({"SPY": 101, "TLT": 102})
    mp, missing = resolve(["SPY", "TLT", "GLD"], search, override={}, cache={})
    assert mp == {"SPY": 101, "TLT": 102}
    assert missing == ["GLD"]


def test_override_wins_over_search():
    search = _fake_search({"SPY": 101})
    mp, missing = resolve(["SPY"], search, override={"SPY": 999}, cache={})
    assert mp["SPY"] == 999
    assert missing == []


def test_cache_used_without_search():
    calls = []
    def search(t): calls.append(t); return None
    mp, _ = resolve(["SPY"], search, override={}, cache={"SPY": 101})
    assert mp["SPY"] == 101 and calls == []


def test_renormalize_over_available():
    w = {"SPY": 0.5, "TLT": -0.5, "GLD": 0.5}
    out = renormalize(w, available=["SPY", "TLT"])
    assert set(out) == {"SPY", "TLT"}
    assert abs(sum(abs(v) for v in out.values()) - 1.0) < 1e-9
