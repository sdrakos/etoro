"""On-disk cache of the eToro instrument catalog: symbol -> instrumentId plus
daily change %, sentiment, and exchange. Populated from /instruments/discover."""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    symbol             TEXT PRIMARY KEY,
    instrument_id      INTEGER NOT NULL,
    exchange_id        INTEGER,
    exchange_name      TEXT,
    display_name       TEXT,
    type_id            INTEGER,
    daily_change       REAL,
    sentiment_buy_pct  REAL,
    is_open            INTEGER,
    updated_at         REAL
);
CREATE INDEX IF NOT EXISTS idx_instruments_id ON instruments(instrument_id);
"""


class EtoroCatalog:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def upsert(self, rows: Iterable[dict], now: Optional[float] = None) -> int:
        now = now if now is not None else time.time()
        payload = []
        for r in rows:
            sym = (r.get("symbol") or "").upper()
            if not sym or r.get("instrument_id") is None:
                continue
            payload.append((
                sym, int(r["instrument_id"]), r.get("exchange_id"), r.get("exchange_name"),
                r.get("display_name"), r.get("type_id"), r.get("daily_change"),
                r.get("sentiment_buy_pct"), r.get("is_open"), now,
            ))
        if not payload:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO instruments
                    (symbol, instrument_id, exchange_id, exchange_name, display_name,
                     type_id, daily_change, sentiment_buy_pct, is_open, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    instrument_id=excluded.instrument_id, exchange_id=excluded.exchange_id,
                    exchange_name=excluded.exchange_name, display_name=excluded.display_name,
                    type_id=excluded.type_id, daily_change=excluded.daily_change,
                    sentiment_buy_pct=excluded.sentiment_buy_pct, is_open=excluded.is_open,
                    updated_at=excluded.updated_at
            """, payload)
            return len(payload)

    def get_many(self, symbols: Iterable[str]) -> dict[str, dict]:
        syms = [s.upper() for s in symbols]
        if not syms:
            return {}
        placeholders = ",".join("?" * len(syms))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE symbol IN ({placeholders})", syms
            ).fetchall()
        return {r["symbol"]: dict(r) for r in rows}

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
