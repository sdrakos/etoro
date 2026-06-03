#!/usr/bin/env python3
"""Claude Code Stop hook: append the session transcript into a local SQLite DB.

Wired from `.claude/settings.json` as a `Stop` hook. On each turn the hook passes
JSON on stdin that includes `transcript_path` and `session_id`. We read the JSONL
transcript and UPSERT every message (keyed by its uuid) into `etoro/claude.db`, so
the conversation survives after the session closes. Idempotent and fast — stdlib only.
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "claude.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    uuid        TEXT PRIMARY KEY,
    session_id  TEXT,
    ts          TEXT,
    role        TEXT,
    type        TEXT,
    text        TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, ts);
"""


def _text_of(message: dict) -> str:
    """Flatten a transcript message's content to plain text."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                parts.append(f"[tool_use: {block.get('name', '')}]")
            elif btype == "tool_result":
                parts.append("[tool_result]")
            elif btype == "thinking":
                parts.append("[thinking]")
        return "\n".join(p for p in parts if p)
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never block the session on a bad payload
    transcript_path = payload.get("transcript_path")
    session_id = payload.get("session_id", "")
    if not transcript_path or not Path(transcript_path).exists():
        return 0

    rows = []
    for line in Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        uuid = obj.get("uuid")
        msg = obj.get("message")
        if not uuid or not isinstance(msg, dict):
            continue
        rows.append((
            uuid,
            obj.get("sessionId", session_id),
            obj.get("timestamp", ""),
            msg.get("role", obj.get("type", "")),
            obj.get("type", ""),
            _text_of(msg),
        ))

    if not rows:
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO messages (uuid, session_id, ts, role, type, text) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(uuid) DO UPDATE SET text=excluded.text",
            rows,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
