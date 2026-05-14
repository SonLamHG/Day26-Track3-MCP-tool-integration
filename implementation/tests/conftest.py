"""Shared fixtures: each test gets a fresh, isolated SQLite DB."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import SQLiteAdapter  # noqa: E402
from init_db import create_database  # noqa: E402


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "lab.db"
    create_database(p)
    return p


@pytest.fixture()
def adapter(db_path: Path) -> SQLiteAdapter:
    return SQLiteAdapter(db_path)


@pytest.fixture()
def server_module(db_path: Path, monkeypatch):
    """Import a fresh copy of mcp_server pointed at the temp DB."""
    monkeypatch.setenv("LAB_DB_PATH", str(db_path))
    # force re-import so module-level adapter sees the env var
    for mod in ("mcp_server",):
        sys.modules.pop(mod, None)
    import mcp_server  # noqa: WPS433
    return mcp_server
