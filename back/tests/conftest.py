from pathlib import Path
import pytest


@pytest.fixture
def temp_db(tmp_path: Path):
    return tmp_path / "metadata.db"
