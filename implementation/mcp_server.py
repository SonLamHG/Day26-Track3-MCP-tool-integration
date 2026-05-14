"""FastMCP server exposing SQLite via search/insert/aggregate tools and schema resources."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from db import SQLiteAdapter, ValidationError
from init_db import create_database

DB_PATH = Path(os.environ.get("LAB_DB_PATH", Path(__file__).resolve().parent / "lab.db"))
_backend = os.environ.get("LAB_BACKEND", "sqlite").lower()
if _backend == "postgres":
    from pg import PostgresAdapter
    adapter = PostgresAdapter(os.environ["LAB_PG_URL"])
else:
    create_database(DB_PATH)
    adapter = SQLiteAdapter(DB_PATH)

MAX_ROWS_RETURNED = 200
MAX_RESPONSE_CHARS = int(os.environ.get("MCP_MAX_RESPONSE_CHARS", 80_000))


def _with_output_hints(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows")
    if isinstance(rows, list) and len(rows) > MAX_ROWS_RETURNED:
        payload["rows"] = rows[:MAX_ROWS_RETURNED]
        payload["truncated"] = True
        payload["truncated_at"] = MAX_ROWS_RETURNED
        payload["hint"] = (
            f"Result truncated. Use 'limit' and 'offset' to paginate "
            f"(MAX_LIMIT={MAX_ROWS_RETURNED})."
        )
    encoded = json.dumps(payload, default=str)
    if len(encoded) > MAX_RESPONSE_CHARS:
        return {
            "table": payload.get("table"),
            "truncated": True,
            "hint": (
                "Response exceeded character budget. Reduce 'limit' "
                "or project fewer columns."
            ),
        }
    return payload


mcp = FastMCP("SQLite Lab MCP Server")


def _safe(call):
    try:
        return call()
    except ValidationError as e:
        # FastMCP turns raised exceptions into tool errors visible to the client.
        raise ValueError(str(e)) from e


@mcp.tool(
    name="search",
    description=(
        "Search rows in a table with optional filters, projection, ordering and pagination. "
        "filters is a list of {column, op, value}. Supported ops: eq, ne, lt, lte, gt, gte, "
        "like, in, is_null. Use limit (default 20, max 500) and offset for pagination — "
        "the response includes 'total_matching' and 'has_more'."
    ),
)
def search(
    table: str,
    columns: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    return _with_output_hints(_safe(lambda: adapter.search(
        table,
        columns=columns,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        descending=descending,
    )))


@mcp.tool(
    name="insert",
    description="Insert a row into a table. values is a {column: value} mapping; returns the inserted row.",
)
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    return _with_output_hints(_safe(lambda: adapter.insert(table, values)))


@mcp.tool(
    name="aggregate",
    description=(
        "Compute an aggregate (count, sum, avg, min, max) over a table, "
        "optionally filtered and grouped."
    ),
)
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    return _with_output_hints(_safe(lambda: adapter.aggregate(
        table,
        metric=metric,
        column=column,
        filters=filters,
        group_by=group_by,
    )))


@mcp.resource(
    uri="schema://database",
    name="database_schema",
    description="Full schema snapshot of every non-internal table in the database.",
    mime_type="application/json",
)
def database_schema() -> str:
    snapshot = {
        "database": str(DB_PATH),
        "tables": {t: adapter.get_table_schema(t) for t in adapter.list_tables()},
    }
    return json.dumps(snapshot, indent=2, default=str)


@mcp.resource(
    uri="schema://table/{table_name}",
    name="table_schema",
    description="Schema for a single table, addressed by name.",
    mime_type="application/json",
)
def table_schema(table_name: str) -> str:
    try:
        cols = adapter.get_table_schema(table_name)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    return json.dumps({"table": table_name, "columns": cols}, indent=2, default=str)


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    _main()
