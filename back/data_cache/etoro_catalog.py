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
    current_rate       REAL,
    asset_class        TEXT,
    updated_at         REAL
);
CREATE INDEX IF NOT EXISTS idx_instruments_id ON instruments(instrument_id);
CREATE INDEX IF NOT EXISTS idx_instruments_asset ON instruments(asset_class);
CREATE INDEX IF NOT EXISTS idx_instruments_exchange ON instruments(exchange_name);
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
                r.get("sentiment_buy_pct"), r.get("is_open"), r.get("current_rate"),
                r.get("asset_class"), now,
            ))
        if not payload:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO instruments
                    (symbol, instrument_id, exchange_id, exchange_name, display_name,
                     type_id, daily_change, sentiment_buy_pct, is_open, current_rate,
                     asset_class, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    instrument_id=excluded.instrument_id, exchange_id=excluded.exchange_id,
                    exchange_name=excluded.exchange_name, display_name=excluded.display_name,
                    type_id=excluded.type_id, daily_change=excluded.daily_change,
                    sentiment_buy_pct=excluded.sentiment_buy_pct, is_open=excluded.is_open,
                    current_rate=excluded.current_rate, asset_class=excluded.asset_class,
                    updated_at=excluded.updated_at
                WHERE excluded.asset_class = 'Stocks' OR instruments.asset_class IS NOT 'Stocks'
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

    def query(self, asset_class: str, q: Optional[str] = None, sort: str = "name",
              page: int = 1, page_size: int = 50,
              exchange: Optional[str] = None) -> tuple[list[dict], int]:
        """Return (rows, total) for one asset_class, optionally text-filtered (symbol or
        display_name contains q) and exchange-filtered, sorted by display_name ('name')
        or symbol, paginated."""
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        where = "asset_class = ?"
        params: list = [asset_class]
        if q:
            where += " AND (UPPER(symbol) LIKE ? OR UPPER(display_name) LIKE ?)"
            like = f"%{q.upper()}%"
            params += [like, like]
        if exchange:
            where += " AND exchange_name = ?"
            params.append(exchange)
        order = "display_name" if sort == "name" else "symbol"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM instruments WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE {where} ORDER BY {order} "
                f"LIMIT ? OFFSET ?", params + [page_size, (page - 1) * page_size]).fetchall()
        return [dict(r) for r in rows], total

    def all_for_category(self, asset_class: str, q: Optional[str] = None,
                         exchange: Optional[str] = None) -> list[dict]:
        """All rows for one asset_class (no pagination), optional text + exchange filter.
        For in-memory sort by computed live fields."""
        where = "asset_class = ?"
        params: list = [asset_class]
        if q:
            where += " AND (UPPER(symbol) LIKE ? OR UPPER(display_name) LIKE ?)"
            like = f"%{q.upper()}%"
            params += [like, like]
        if exchange:
            where += " AND exchange_name = ?"
            params.append(exchange)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE {where} ORDER BY display_name", params).fetchall()
        return [dict(r) for r in rows]

    def exchanges(self, asset_class: str) -> list[dict]:
        """Distinct exchanges for one asset_class with instrument counts, busiest first.
        Skips NULL/empty exchange names. Return: [{"exchange": str, "count": int}, ...]."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT exchange_name AS exchange, COUNT(*) AS count FROM instruments "
                "WHERE asset_class = ? AND exchange_name IS NOT NULL AND exchange_name <> '' "
                "GROUP BY exchange_name ORDER BY count DESC, exchange_name",
                (asset_class,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_instrument_ids(self, ids: Iterable[int]) -> dict[int, dict]:
        """Map instrument_id -> catalog row for the given ids. Unknown ids are omitted."""
        idlist = [int(i) for i in ids if i is not None]
        if not idlist:
            return {}
        placeholders = ",".join("?" * len(idlist))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM instruments WHERE instrument_id IN ({placeholders})", idlist
            ).fetchall()
        return {r["instrument_id"]: dict(r) for r in rows}
