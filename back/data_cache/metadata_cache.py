"""SQLite cache for slow-changing screener fields (market cap, P/E)."""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS screener_metadata (
    ticker     TEXT PRIMARY KEY,
    market_cap REAL,
    pe_ratio   REAL,
    updated_at INTEGER NOT NULL
);
"""

TTL_MS = 24 * 60 * 60 * 1000  # 24 hours


class MetadataCache:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def get(self, ticker: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT market_cap, pe_ratio, updated_at FROM screener_metadata WHERE ticker = ?",
                (ticker,),
            ).fetchone()
        if row is None:
            return None
        return {"market_cap": row[0], "pe_ratio": row[1], "updated_at": int(row[2])}

    def is_stale(self, entry: Optional[dict], now_ms: Optional[int] = None) -> bool:
        if entry is None:
            return True
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        return (now_ms - entry["updated_at"]) > TTL_MS

    def put(self, ticker: str, market_cap: Optional[float], pe_ratio: Optional[float],
            now_ms: Optional[int] = None) -> None:
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO screener_metadata (ticker, market_cap, pe_ratio, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    market_cap = excluded.market_cap,
                    pe_ratio   = excluded.pe_ratio,
                    updated_at = excluded.updated_at
            """, (ticker, market_cap, pe_ratio, now_ms))
