"""PostgreSQL adapter mirroring SQLiteAdapter's surface.

Optional dependency: ``psycopg``. Only imported when this module is used.
"""
from __future__ import annotations

from typing import Any, Iterable

from db import MAX_LIMIT, SUPPORTED_METRICS, SUPPORTED_OPERATORS, ValidationError


class PostgresAdapter:
    def __init__(self, dsn: str):
        import psycopg  # local import: optional dependency
        from psycopg.rows import dict_row
        self._psycopg = psycopg
        self._dict_row = dict_row
        self.dsn = dsn

    def _connect(self):
        return self._psycopg.connect(self.dsn, row_factory=self._dict_row)

    # ---------- inspection ----------
    def list_tables(self) -> list[str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
            return [r["tablename"] for r in cur.fetchall()]

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        self._validate_table(table)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            cols = cur.fetchall()
            cur.execute(
                """
                SELECT a.attname AS name
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                                   AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass AND i.indisprimary
                """,
                (table,),
            )
            pk_names = {r["name"] for r in cur.fetchall()}
        return [
            {
                "name": c["column_name"],
                "type": c["data_type"],
                "notnull": c["is_nullable"] == "NO",
                "default": c["column_default"],
                "primary_key": c["column_name"] in pk_names,
            }
            for c in cols
        ]

    # ---------- validation ----------
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

    def _build_where(self, table, filters):
        if not filters:
            return "", []
        if not isinstance(filters, list):
            raise ValidationError("filters must be a list of {column, op, value} objects.")
        clauses, params = [], []
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
                placeholders = ", ".join("%s" * len(vals))
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(vals)
            else:
                if "value" not in f:
                    raise ValidationError(f"Operator {op!r} requires a 'value'.")
                clauses.append(f"{col} {sql_op} %s")
                params.append(f["value"])
        return " WHERE " + " AND ".join(clauses), params

    # ---------- search / insert / aggregate ----------
    def search(self, table, columns=None, filters=None, limit=20, offset=0,
               order_by=None, descending=False):
        self._validate_table(table)
        if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            raise ValidationError(f"limit must be 1..{MAX_LIMIT}.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be >= 0.")
        if columns:
            self._validate_columns(table, columns)
            projection = ", ".join(columns)
        else:
            projection = "*"
        where_sql, params = self._build_where(table, filters or [])
        order_sql = ""
        if order_by is not None:
            self._validate_columns(table, [order_by])
            order_sql = f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
        sql = f"SELECT {projection} FROM {table}{where_sql}{order_sql} LIMIT %s OFFSET %s"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, [*params, limit, offset])
            rows = list(cur.fetchall())
            cur.execute(f"SELECT COUNT(*) AS c FROM {table}{where_sql}", params)
            total = cur.fetchone()["c"]
        return {"table": table, "rows": rows, "count": len(rows),
                "total_matching": total, "limit": limit, "offset": offset,
                "has_more": offset + len(rows) < total}

    def insert(self, table, values):
        self._validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("values must be a non-empty mapping of column -> value.")
        self._validate_columns(table, values.keys())
        cols = list(values.keys())
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING *"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, [values[c] for c in cols])
            row = cur.fetchone()
            conn.commit()
        return {"table": table, "inserted_id": row.get("id"), "row": row}

    def aggregate(self, table, metric, column=None, filters=None, group_by=None):
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
        sql = f"SELECT {select_extra}{metric_expr} AS value FROM {table}{where_sql}{group_sql}"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = list(cur.fetchall())
        return {"table": table, "metric": metric, "column": column,
                "group_by": group_by, "rows": rows}
