import sqlite3
import pandas as pd
from trader.data.cache import Cache

OLD_SCHEMA = """
CREATE TABLE bars (
    ticker TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, vwap REAL,
    adjusted INTEGER DEFAULT 1,
    timespan TEXT DEFAULT 'day',
    PRIMARY KEY (ticker, timestamp, timespan)
);
"""


def test_old_db_migrates_and_tags_rows_as_massive(tmp_path):
    db = tmp_path / "cache.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(OLD_SCHEMA)
        conn.execute(
            "INSERT INTO bars (ticker, timestamp, open, high, low, close, volume, vwap, adjusted, timespan) "
            "VALUES ('AAPL', 1700000000000, 1, 1, 1, 1, 1, 1, 1, 'day')"
        )

    cache = Cache(db)  # opening triggers migration

    with sqlite3.connect(db) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bars)")]
    assert "source" in cols

    df = cache.query("AAPL", 0, 1_800_000_000_000, source="massive")
    assert len(df) == 1


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "cache.db"
    Cache(db)   # first open — fresh DB
    Cache(db)   # second open — already migrated, must not raise
