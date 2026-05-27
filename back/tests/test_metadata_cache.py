import time
import pytest

from data_cache.metadata_cache import MetadataCache


def test_init_creates_schema(temp_db):
    cache = MetadataCache(temp_db)
    assert cache.get("AAPL") is None  # empty cache returns None


def test_put_then_get_roundtrip(temp_db):
    cache = MetadataCache(temp_db)
    cache.put("AAPL", market_cap=3_500_000_000_000, pe_ratio=32.5)
    entry = cache.get("AAPL")
    assert entry is not None
    assert entry["market_cap"] == 3_500_000_000_000
    assert entry["pe_ratio"] == 32.5
    assert entry["updated_at"] > 0


def test_put_idempotent_updates_in_place(temp_db):
    cache = MetadataCache(temp_db)
    cache.put("AAPL", 1.0, 1.0, now_ms=1_000)
    cache.put("AAPL", 2.0, 2.0, now_ms=2_000)
    entry = cache.get("AAPL")
    assert entry["market_cap"] == 2.0
    assert entry["updated_at"] == 2_000


def test_is_stale_within_ttl_returns_false(temp_db):
    cache = MetadataCache(temp_db)
    cache.put("AAPL", 1.0, 1.0, now_ms=1_000_000)
    entry = cache.get("AAPL")
    assert cache.is_stale(entry, now_ms=1_000_000 + 3_600_000) is False


def test_is_stale_after_ttl_returns_true(temp_db):
    cache = MetadataCache(temp_db)
    cache.put("AAPL", 1.0, 1.0, now_ms=1_000_000)
    entry = cache.get("AAPL")
    assert cache.is_stale(entry, now_ms=1_000_000 + 25 * 3_600_000) is True


def test_is_stale_none_entry_returns_true(temp_db):
    cache = MetadataCache(temp_db)
    assert cache.is_stale(None) is True


def test_put_handles_null_fields(temp_db):
    cache = MetadataCache(temp_db)
    cache.put("XYZ", market_cap=None, pe_ratio=None)
    entry = cache.get("XYZ")
    assert entry["market_cap"] is None
    assert entry["pe_ratio"] is None
