import sqlite3
from pathlib import Path
import pytest


@pytest.fixture
def temp_db(tmp_path: Path):
    """Fresh SQLite path per test."""
    return tmp_path / "cache.db"
