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

    # ---------- search ----------
    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self._validate_table(table)

        # pagination (validate inputs before building any SQL)
        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit must be a positive integer.")
        if limit > MAX_LIMIT:
            raise ValidationError(f"limit cannot exceed {MAX_LIMIT}.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a non-negative integer.")

        # column projection
        if columns:
            self._validate_columns(table, columns)
            projection = ", ".join(columns)
        else:
            projection = "*"

        # filters
        where_sql, params = self._build_where(table, filters or [])

        # order
        order_sql = ""
        if order_by is not None:
            self._validate_columns(table, [order_by])
            order_sql = f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"

        sql = f"SELECT {projection} FROM {table}{where_sql}{order_sql} LIMIT ? OFFSET ?"
        bound = (*params, limit, offset)

        with self._connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, bound).fetchall()]
            total = conn.execute(
                f"SELECT COUNT(*) AS c FROM {table}{where_sql}", params
            ).fetchone()["c"]

        return {
            "table": table,
            "rows": rows,
            "count": len(rows),
            "total_matching": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
        }

    def _build_where(
        self, table: str, filters: list[dict[str, Any]]
    ) -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        if not isinstance(filters, list):
            raise ValidationError("filters must be a list of {column, op, value} objects.")

        clauses: list[str] = []
        params: list[Any] = []
        for f in filters:
            if not isinstance(f, dict) or "column" not in f or "op" not in f:
                raise ValidationError("Each filter needs 'column' and 'op'.")
            col, op = f["column"], f["op"]
            self._validate_columns(table, [col])
            if op not in SUPPORTED_OPERATORS:
                raise ValidationError(
                    f"Unsupported operator {op!r}. "
                    f"Allowed: {sorted(SUPPORTED_OPERATORS)}"
                )
            sql_op = SUPPORTED_OPERATORS[op]
            if op == "is_null":
                clauses.append(f"{col} IS NULL")
            elif op == "in":
                vals = f.get("value")
                if not isinstance(vals, list) or not vals:
                    raise ValidationError("Operator 'in' requires a non-empty value list.")
                placeholders = ", ".join("?" * len(vals))
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(vals)
            else:
                if "value" not in f:
                    raise ValidationError(f"Operator {op!r} requires a 'value'.")
                clauses.append(f"{col} {sql_op} ?")
                params.append(f["value"])
        return " WHERE " + " AND ".join(clauses), params

    # ---------- insert ----------
    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self._validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("values must be a non-empty mapping of column -> value.")
        self._validate_columns(table, values.keys())

        cols = list(values.keys())
        col_sql = ", ".join(cols)
        placeholders = ", ".join("?" * len(cols))
        params = [values[c] for c in cols]

        sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
        with self._connect() as conn:
            cur = conn.execute(sql, params)
            new_id = cur.lastrowid
            conn.commit()
            row = conn.execute(
                f"SELECT * FROM {table} WHERE rowid = ?", (cur.lastrowid,)
            ).fetchone()

        return {
            "table": table,
            "inserted_id": new_id,
            "row": dict(row) if row else dict(values),
        }

    # ---------- aggregate ----------
    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        self._validate_table(table)

        if metric not in SUPPORTED_METRICS:
            raise ValidationError(
                f"Unsupported metric {metric!r}. "
                f"Allowed: {sorted(SUPPORTED_METRICS)}"
            )
        func = SUPPORTED_METRICS[metric]

        if metric == "count":
            if column is not None:
                self._validate_columns(table, [column])
            metric_expr = "COUNT(*)" if column is None else f"COUNT({column})"
        else:
            if column is None:
                raise ValidationError(f"Metric {metric!r} requires a 'column'.")
            self._validate_columns(table, [column])
            metric_expr = f"{func}({column})"

        where_sql, params = self._build_where(table, filters or [])

        group_sql = ""
        select_extra = ""
        if group_by is not None:
            self._validate_columns(table, [group_by])
            group_sql = f" GROUP BY {group_by}"
            select_extra = f"{group_by}, "

        sql = (
            f"SELECT {select_extra}{metric_expr} AS value "
            f"FROM {table}{where_sql}{group_sql}"
        )
        with self._connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": rows,
        }
