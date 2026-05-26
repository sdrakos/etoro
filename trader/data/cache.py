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
    PRIMARY KEY (ticker, timestamp, timespan)
);
CREATE INDEX IF NOT EXISTS idx_bars_ticker_range
    ON bars(ticker, timespan, timestamp);
"""


class Cache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def upsert(self, bars: Iterable[dict], timespan: str = "day") -> int:
        rows = [(b["ticker"], int(b["timestamp"]),
                 b.get("open"), b.get("high"), b.get("low"), b.get("close"),
                 b.get("volume"), b.get("vwap"), 1, timespan) for b in bars]
        if not rows:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO bars (ticker, timestamp, open, high, low, close,
                                  volume, vwap, adjusted, timespan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, timestamp, timespan) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, vwap=excluded.vwap
            """, rows)
            return conn.total_changes

    def query(self, ticker: str, start_ms: int, end_ms: int,
              timespan: str = "day") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """SELECT timestamp, open, high, low, close, volume, vwap
                   FROM bars
                   WHERE ticker = ? AND timespan = ?
                     AND timestamp BETWEEN ? AND ?
                   ORDER BY timestamp""",
                conn, params=(ticker, timespan, start_ms, end_ms),
            )

    def coverage(self, ticker: str, timespan: str = "day") -> tuple[int, int] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM bars "
                "WHERE ticker = ? AND timespan = ?",
                (ticker, timespan),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return (int(row[0]), int(row[1]))

    def clear(self, ticker: str, timespan: str = "day") -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM bars WHERE ticker = ? AND timespan = ?",
                (ticker, timespan),
            )
            return cur.rowcount

    def list_tickers(self, timespan: str = "day") -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                "SELECT ticker, MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts, "
                "       COUNT(*) AS bar_count "
                "FROM bars WHERE timespan = ? GROUP BY ticker ORDER BY ticker",
                conn, params=(timespan,),
            )
