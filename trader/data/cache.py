from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    ticker     TEXT NOT NULL,
    timestamp  INTEGER NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    vwap       REAL,
    adjusted   INTEGER DEFAULT 1,
    timespan   TEXT DEFAULT 'day',
    source     TEXT NOT NULL DEFAULT 'massive',
    PRIMARY KEY (ticker, timestamp, timespan, source)
);
CREATE INDEX IF NOT EXISTS idx_bars_ticker_range
    ON bars(ticker, timespan, source, timestamp);
"""

# NOTE: The CREATE TABLE bars (...) below must be kept in sync with the SCHEMA string above.
_MIGRATE_ADD_SOURCE = """
ALTER TABLE bars RENAME TO bars_old;
CREATE TABLE bars (
    ticker     TEXT NOT NULL,
    timestamp  INTEGER NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    vwap       REAL,
    adjusted   INTEGER DEFAULT 1,
    timespan   TEXT DEFAULT 'day',
    source     TEXT NOT NULL DEFAULT 'massive',
    PRIMARY KEY (ticker, timestamp, timespan, source)
);
INSERT INTO bars (ticker, timestamp, open, high, low, close,
                  volume, vwap, adjusted, timespan, source)
    SELECT ticker, timestamp, open, high, low, close,
           volume, vwap, adjusted, timespan, 'massive'
    FROM bars_old;
DROP TABLE bars_old;
"""


class Cache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with sqlite3.connect(self.db_path) as conn:
            self._migrate(conn)
            conn.executescript(SCHEMA)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """One-time upgrade: add `source` to the PK of pre-existing DBs."""
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bars'"
        ).fetchone()
        if not exists:
            return  # fresh DB — SCHEMA creates the new table
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bars)")]
        if "source" in cols:
            return  # already migrated
        conn.executescript(_MIGRATE_ADD_SOURCE)

    def upsert(self, bars: Iterable[dict], timespan: str = "day",
               source: str = "massive") -> int:
        rows = [(b["ticker"], int(b["timestamp"]),
                 b.get("open"), b.get("high"), b.get("low"), b.get("close"),
                 b.get("volume"), b.get("vwap"), 1, timespan, source) for b in bars]
        if not rows:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO bars (ticker, timestamp, open, high, low, close,
                                  volume, vwap, adjusted, timespan, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, timestamp, timespan, source) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, vwap=excluded.vwap
            """, rows)
            return conn.total_changes

    def query(self, ticker: str, start_ms: int, end_ms: int,
              timespan: str = "day", source: str = "massive") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT timestamp, open, high, low, close, volume, vwap
                   FROM bars
                   WHERE ticker = ? AND timespan = ? AND source = ?
                     AND timestamp BETWEEN ? AND ?
                   ORDER BY timestamp""",
                conn, params=(ticker, timespan, source, start_ms, end_ms),
            )

    def coverage(self, ticker: str, timespan: str = "day",
                 source: str = "massive") -> tuple[int, int] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM bars "
                "WHERE ticker = ? AND timespan = ? AND source = ?",
                (ticker, timespan, source),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return (int(row[0]), int(row[1]))

    def clear(self, ticker: str, timespan: str = "day",
              source: str | None = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            if source is None:
                cur = conn.execute(
                    "DELETE FROM bars WHERE ticker = ? AND timespan = ?",
                    (ticker, timespan),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM bars WHERE ticker = ? AND timespan = ? AND source = ?",
                    (ticker, timespan, source),
                )
            return cur.rowcount

    def list_tickers(self, timespan: str = "day") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                "SELECT ticker, source, MIN(timestamp) AS min_ts, "
                "       MAX(timestamp) AS max_ts, COUNT(*) AS bar_count "
                "FROM bars WHERE timespan = ? "
                "GROUP BY ticker, source ORDER BY ticker, source",
                conn, params=(timespan,),
            )
