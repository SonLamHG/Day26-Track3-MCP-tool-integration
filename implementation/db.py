"""SQLite adapter for the FastMCP lab.

All identifier-bearing inputs (table names, column names, operators, metrics,
order direction, group_by) are validated against whitelists derived from the
live database schema BEFORE being interpolated into SQL. All value-bearing
inputs are passed as bound parameters.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Protocol


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


SUPPORTED_OPERATORS: dict[str, str] = {
    "eq":      "=",
    "ne":      "!=",
    "lt":      "<",
    "lte":     "<=",
    "gt":      ">",
    "gte":     ">=",
    "like":    "LIKE",
    "in":      "IN",
    "is_null": "IS NULL",
}

SUPPORTED_METRICS: dict[str, str] = {
    "count": "COUNT",
    "sum":   "SUM",
    "avg":   "AVG",
    "min":   "MIN",
    "max":   "MAX",
}

MAX_LIMIT = 500


class DatabaseAdapter(Protocol):
    """Shared interface so a Postgres adapter can be swapped in."""

    def list_tables(self) -> list[str]: ...
    def get_table_schema(self, table: str) -> list[dict[str, Any]]: ...
    def search(self, table: str, **kwargs: Any) -> dict[str, Any]: ...
    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]: ...
    def aggregate(self, table: str, metric: str, **kwargs: Any) -> dict[str, Any]: ...


class SQLiteAdapter:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    # ---------- connection ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ---------- inspection ----------
    def list_tables(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        return [r["name"] for r in rows]

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        self._validate_table(table)
        with self._connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [
            {
                "name":       r["name"],
                "type":       r["type"],
                "notnull":    bool(r["notnull"]),
                "default":    r["dflt_value"],
                "primary_key": bool(r["pk"]),
            }
            for r in rows
        ]

    # ---------- validation helpers ----------
    def _validate_table(self, table: str) -> None:
        if not isinstance(table, str) or not table:
            raise ValidationError("Table name must be a non-empty string.")
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table!r}")

    def _validate_columns(self, table: str, columns: Iterable[str]) -> None:
        known = {c["name"] for c in self.get_table_schema(table)}
        for col in columns:
            if col not in known:
                raise ValidationError(f"Unknown column {col!r} on table {table!r}")
