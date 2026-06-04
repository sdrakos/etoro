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


def test_query_filters_by_asset_class_and_paginates(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": f"S{i}", "instrument_id": i, "asset_class": "Stocks",
                 "display_name": f"Stock {i}"} for i in range(1, 6)]
               + [{"symbol": "BTC", "instrument_id": 100, "asset_class": "Crypto",
                   "display_name": "Bitcoin"}])
    rows, total = cat.query("Stocks", page=1, page_size=2)
    assert total == 5 and len(rows) == 2
    rows2, total2 = cat.query("Crypto")
    assert total2 == 1 and rows2[0]["symbol"] == "BTC"


def test_query_text_filter(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks", "display_name": "Apple"},
                {"symbol": "MSFT", "instrument_id": 2, "asset_class": "Stocks", "display_name": "Microsoft"}])
    rows, total = cat.query("Stocks", q="apple")
    assert total == 1 and rows[0]["symbol"] == "AAPL"


def test_query_name_sort(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": "Z", "instrument_id": 1, "asset_class": "Stocks", "display_name": "Zeta"},
                {"symbol": "A", "instrument_id": 2, "asset_class": "Stocks", "display_name": "Alpha"}])
    rows, _ = cat.query("Stocks", sort="name")
    assert [r["display_name"] for r in rows] == ["Alpha", "Zeta"]


def test_all_for_category_returns_everything(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([{"symbol": f"S{i}", "instrument_id": i, "asset_class": "Stocks",
                 "display_name": f"Stock {i}"} for i in range(1, 301)])  # 300 > 200 clamp
    rows = cat.all_for_category("Stocks")
    assert len(rows) == 300
    # text filter still applies
    cat.upsert([{"symbol": "AAPL", "instrument_id": 9999, "asset_class": "Stocks", "display_name": "Apple"}])
    assert len(cat.all_for_category("Stocks", q="apple")) == 1


def test_exchanges_distinct_counts_sorted(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks", "exchange_name": "Nasdaq"},
        {"symbol": "MSFT", "instrument_id": 2, "asset_class": "Stocks", "exchange_name": "Nasdaq"},
        {"symbol": "JPM", "instrument_id": 3, "asset_class": "Stocks", "exchange_name": "NYSE"},
        {"symbol": "BTC", "instrument_id": 4, "asset_class": "Crypto", "exchange_name": "Digital Currency"},
        {"symbol": "NOEXCH", "instrument_id": 5, "asset_class": "Stocks", "exchange_name": None},
    ])
    ex = cat.exchanges("Stocks")
    assert ex == [{"exchange": "Nasdaq", "count": 2}, {"exchange": "NYSE", "count": 1}]
    assert cat.exchanges("Crypto") == [{"exchange": "Digital Currency", "count": 1}]


def test_query_and_all_for_category_exchange_filter(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1, "asset_class": "Stocks", "exchange_name": "Nasdaq",
         "display_name": "Apple"},
        {"symbol": "JPM", "instrument_id": 2, "asset_class": "Stocks", "exchange_name": "NYSE",
         "display_name": "JPMorgan"},
    ])
    rows, total = cat.query("Stocks", exchange="Nasdaq")
    assert total == 1 and [r["symbol"] for r in rows] == ["AAPL"]
    allrows = cat.all_for_category("Stocks", exchange="NYSE")
    assert [r["symbol"] for r in allrows] == ["JPM"]
    _, total_all = cat.query("Stocks")
    assert total_all == 2


def test_get_by_instrument_ids(tmp_path):
    from data_cache.etoro_catalog import EtoroCatalog
    cat = EtoroCatalog(tmp_path / "c.db")
    cat.upsert([
        {"symbol": "AAPL", "instrument_id": 1001, "asset_class": "Stocks",
         "display_name": "Apple", "exchange_name": "Nasdaq", "current_rate": 210.0},
        {"symbol": "MSFT", "instrument_id": 1002, "asset_class": "Stocks",
         "display_name": "Microsoft", "exchange_name": "Nasdaq", "current_rate": 400.0},
    ])
    m = cat.get_by_instrument_ids([1001, 99999])
    assert set(m.keys()) == {1001}
    assert m[1001]["symbol"] == "AAPL" and m[1001]["current_rate"] == 210.0
    assert cat.get_by_instrument_ids([]) == {}
