from data_cache.etoro_catalog import EtoroCatalog


def test_upsert_and_get_many_case_insensitive(tmp_path):
    cat = EtoroCatalog(tmp_path / "cat.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1001, "exchange_name": "NASDAQ",
         "display_name": "Apple", "type_id": 5, "daily_change": 1.2,
         "sentiment_buy_pct": 80.0, "is_open": 1},
        {"symbol": "MSFT", "instrument_id": 1002, "exchange_name": "NASDAQ",
         "display_name": "Microsoft", "type_id": 5, "daily_change": -0.5,
         "sentiment_buy_pct": 70.0, "is_open": 1},
    ])
    got = cat.get_many(["aapl", "MSFT", "ZZZ"])
    assert set(got) == {"AAPL", "MSFT"}
    assert got["AAPL"]["instrument_id"] == 1001
    assert got["AAPL"]["daily_change"] == 1.2
    assert got["MSFT"]["sentiment_buy_pct"] == 70.0


def test_upsert_is_idempotent_and_updates(tmp_path):
    cat = EtoroCatalog(tmp_path / "cat.db")
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1001, "daily_change": 1.0}])
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1001, "daily_change": 2.0}])
    got = cat.get_many(["AAPL"])
    assert len(got) == 1 and got["AAPL"]["daily_change"] == 2.0


def test_count(tmp_path):
    cat = EtoroCatalog(tmp_path / "cat.db")
    assert cat.count() == 0
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1}])
    assert cat.count() == 1
