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


def test_upsert_stores_current_rate(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "cat.db")
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1001, "current_rate": 310.26}])
    got = cat.get_many(["AAPL"])
    assert got["AAPL"]["current_rate"] == 310.26


def test_upsert_prefers_stocks_on_symbol_collision(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "cat.db")
    # crypto "ABT" inserted first, then the Abbott stock with same symbol
    cat.upsert([{"symbol": "ABT", "instrument_id": 9000, "asset_class": "Crypto",
                 "exchange_name": "Digital Currency", "current_rate": 0.21}])
    cat.upsert([{"symbol": "ABT", "instrument_id": 100594, "asset_class": "Stocks",
                 "exchange_name": "NYSE", "current_rate": 130.0}])
    got = cat.get_many(["ABT"])
    assert got["ABT"]["instrument_id"] == 100594   # stock wins
    assert got["ABT"]["asset_class"] == "Stocks"

    # reverse order: stock first, crypto second -> stock must NOT be overwritten
    cat2 = EtoroCatalog(tmp_path / "cat2.db")
    cat2.upsert([{"symbol": "ABT", "instrument_id": 100594, "asset_class": "Stocks",
                  "exchange_name": "NYSE", "current_rate": 130.0}])
    cat2.upsert([{"symbol": "ABT", "instrument_id": 9000, "asset_class": "Crypto",
                  "exchange_name": "Digital Currency", "current_rate": 0.21}])
    got2 = cat2.get_many(["ABT"])
    assert got2["ABT"]["instrument_id"] == 100594  # stock kept


def test_upsert_within_single_batch_prefers_stocks(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "cat.db")
    cat.upsert([
        {"symbol": "ABT", "instrument_id": 9000, "asset_class": "Crypto"},
        {"symbol": "ABT", "instrument_id": 100594, "asset_class": "Stocks"},
    ])
    assert cat.get_many(["ABT"])["ABT"]["instrument_id"] == 100594
