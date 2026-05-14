# SQLite FastMCP Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-quality FastMCP server in Python that exposes a SQLite database through `search`, `insert`, and `aggregate` tools plus schema resources, achieving 100/100 on the rubric plus the full 10-point bonus.

**Architecture:** A thin FastMCP layer (`mcp_server.py`) delegates to an `SQLiteAdapter` (`db.py`) that owns connection management, identifier validation, and parameterized SQL. The database is reproducibly initialized via `init_db.py` with a `students` / `courses` / `enrollments` schema. A separate `pg.py` PostgreSQL adapter behind the same `DatabaseAdapter` Protocol unlocks the dual-backend bonus. Verification is automated through `verify_server.py` plus a `pytest` suite, and Inspector/Claude Code/Codex/Gemini CLI configs are committed alongside the code.

**Tech Stack:** Python 3.10+, `fastmcp>=2`, `sqlite3` (stdlib), `pytest`, `psycopg[binary]` (bonus), Node-based `@modelcontextprotocol/inspector` for manual verification.

**Scoring map (target = 110/100):**

| Rubric section | Pts | How the plan earns it |
|---|---|---|
| 1. Server Foundation | 20 | Tasks 1, 2, 3 (clean layout, reproducible DB, separated concerns) |
| 2. Required Tools | 30 | Tasks 4, 5, 6, 7 (search w/ filters+order+pagination, insert w/ payload, aggregate w/ 5 metrics) |
| 3. MCP Resources | 15 | Task 8 (schema://database + schema://table/{name}) |
| 4. Safety & Errors | 15 | Tasks 3-7 (whitelist identifiers, operator allow-list, parameterized SQL, ValidationError) |
| 5. Verification | 10 | Tasks 9, 10 (pytest + verify_server.py exercising success & failure paths) |
| 6. Client + Demo | 10 | Tasks 11, 12, 13 (Inspector helper, `.mcp.json`, README, demo script) |
| Bonus | +10 | Task 14 (HTTP+bearer auth), Task 15 (Postgres adapter), Task 16 (pagination metadata + output cap) |

---

## File Structure

```
Day26-Track3-MCP-tool-integration/
├── implementation/
│   ├── requirements.txt              # fastmcp, pytest, psycopg[binary] (bonus)
│   ├── db.py                         # SQLiteAdapter + ValidationError + DatabaseAdapter Protocol
│   ├── pg.py                         # (bonus) PostgresAdapter using same Protocol
│   ├── init_db.py                    # creates students/courses/enrollments + seed rows
│   ├── mcp_server.py                 # FastMCP server: tools + resources + transport entrypoint
│   ├── verify_server.py              # programmatic smoke test via fastmcp.Client
│   ├── start_inspector.sh            # convenience wrapper for MCP Inspector
│   ├── start_inspector.ps1           # Windows equivalent
│   ├── .mcp.json.example             # Claude Code config snippet
│   ├── codex_config.example.toml     # Codex config snippet
│   ├── gemini_settings.example.json  # Gemini settings snippet
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py               # isolated tmp DB per test
│       ├── test_db.py                # SQLiteAdapter unit tests (success + ValidationError)
│       └── test_server.py            # FastMCP in-memory client integration tests
├── docs/superpowers/plans/2026-05-14-sqlite-fastmcp-lab.md  # this file
├── README.md                         # add Setup/Run/Demo/Client sections
└── DEMO.md                           # demo script for the 2-minute video
```

Responsibilities:

- `db.py` — owns *all* SQL construction and identifier whitelisting. The MCP layer never builds SQL strings.
- `init_db.py` — single source of truth for schema + seed; idempotent.
- `mcp_server.py` — thin: parses args, builds adapter, registers tools/resources, runs transport.
- `verify_server.py` — uses `fastmcp.Client` against the stdio server to assert discovery + success + failure shape.
- Tests — `test_db.py` covers adapter rules without MCP; `test_server.py` uses FastMCP's in-memory client.

---

## Working Directory & Shell Notes

- All paths below are **relative to** `d:\code\AI-VinUni\Day26-Track3-MCP-tool-integration\`.
- Shell is **PowerShell 7+** by default. Use `;` to chain unconditionally, `&&` only when later commands depend on earlier success.
- Python launcher on Windows: prefer `py -3.11` (or whichever the user has). Substitute with `python` if `py` is unavailable. The plan uses `py -3.11` consistently — the engineer should pick the interpreter installed locally and use it for all subsequent commands.
- All file writes use **UTF-8 without BOM**.

---

### Task 1: Project Skeleton & Dependencies

**Files:**
- Create: `implementation/requirements.txt`
- Create: `implementation/__init__.py` (empty marker for cleanliness; optional but lets tests import the package)
- Create: `implementation/tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`** (root)

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.npm-cache/
implementation/lab.db
implementation/*.db
.env
```

- [ ] **Step 2: Create `implementation/requirements.txt`**

```
fastmcp>=2.0.0
pytest>=8.0.0
psycopg[binary]>=3.2.0
```

(`psycopg` is only imported lazily inside `pg.py` for the bonus task — installation is optional for the base grade. Add a comment in the file explaining this.)

- [ ] **Step 3: Create the empty marker files**

`implementation/__init__.py` — empty.
`implementation/tests/__init__.py` — empty.

- [ ] **Step 4: Build and activate the virtualenv, install dependencies**

PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r implementation/requirements.txt
```

Expected: `fastmcp`, `pytest`, `psycopg` all installed without error. Record the python path (`(Get-Command python).Source`) — needed later for MCP client configs.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore implementation/requirements.txt implementation/__init__.py implementation/tests/__init__.py
git commit -m "chore: scaffold implementation package and dependencies"
```

---

### Task 2: Database Initialization (`init_db.py`)

**Files:**
- Create: `implementation/init_db.py`
- Test: covered indirectly by `tests/conftest.py` in Task 9

- [ ] **Step 1: Write `implementation/init_db.py`**

```python
"""Initialize the SQLite lab database with schema and seed data.

Idempotent: running twice produces the same final state. The DB file path is
controlled by the LAB_DB_PATH environment variable, defaulting to
``implementation/lab.db`` resolved relative to this file's parent.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "lab.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL,
    cohort    TEXT    NOT NULL,
    score     REAL    NOT NULL DEFAULT 0,
    email     TEXT    UNIQUE
);

CREATE TABLE IF NOT EXISTS courses (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT    NOT NULL UNIQUE,
    title     TEXT    NOT NULL,
    credits   INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE IF NOT EXISTS enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    grade       REAL,
    UNIQUE(student_id, course_id)
);
"""

SEED_ROWS = {
    "students": [
        ("Alice Nguyen",  "A1", 92.5, "alice@example.com"),
        ("Bao Tran",      "A1", 78.0, "bao@example.com"),
        ("Chi Le",        "A2", 85.0, "chi@example.com"),
        ("Dao Pham",      "A2", 64.5, "dao@example.com"),
        ("Eric Vo",       "B1", 88.0, "eric@example.com"),
    ],
    "courses": [
        ("CS101", "Intro to Programming", 3),
        ("CS201", "Data Structures",      4),
        ("MA110", "Linear Algebra",       3),
    ],
    "enrollments": [
        (1, 1, 9.0),
        (1, 2, 8.5),
        (2, 1, 7.0),
        (3, 2, 9.2),
        (4, 3, 6.5),
        (5, 1, 8.8),
        (5, 3, 9.5),
    ],
}


def _seed_if_empty(conn: sqlite3.Connection, table: str, rows: list[tuple]) -> None:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if count:
        return
    placeholders = ", ".join("?" * len(rows[0]))
    columns = {
        "students":    "(name, cohort, score, email)",
        "courses":     "(code, title, credits)",
        "enrollments": "(student_id, course_id, grade)",
    }[table]
    conn.executemany(f"INSERT INTO {table} {columns} VALUES ({placeholders})", rows)


def create_database(db_path: str | os.PathLike | None = None) -> Path:
    path = Path(db_path) if db_path else Path(os.environ.get("LAB_DB_PATH", DEFAULT_DB_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        for table, rows in SEED_ROWS.items():
            _seed_if_empty(conn, table, rows)
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    p = create_database()
    print(f"Initialized database at {p}")
```

- [ ] **Step 2: Run it manually**

```powershell
py -3.11 implementation/init_db.py
```

Expected output: `Initialized database at .../implementation/lab.db`. The file should now exist.

- [ ] **Step 3: Confirm reproducibility (run twice, no duplicate rows)**

```powershell
py -3.11 implementation/init_db.py
py -3.11 -c "import sqlite3; print(sqlite3.connect('implementation/lab.db').execute('SELECT COUNT(*) FROM students').fetchone())"
```

Expected: `(5,)` both before and after the second run.

- [ ] **Step 4: Commit**

```powershell
git add implementation/init_db.py
git commit -m "feat: add reproducible SQLite schema and seed data"
```

---

### Task 3: SQLite Adapter — Connection + Schema Inspection

**Files:**
- Create: `implementation/db.py`
- Test: `implementation/tests/test_db.py` (created in Task 9; placeholder behavior verified manually here)

- [ ] **Step 1: Create `implementation/db.py` with the skeleton**

```python
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
```

(Subsequent tasks append `search`, `insert`, `aggregate` to this same class.)

- [ ] **Step 2: Smoke test inspection in a REPL**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter; a = SQLiteAdapter('implementation/lab.db'); print(a.list_tables()); print(a.get_table_schema('students'))"
```

Expected: `['courses', 'enrollments', 'students']` then a list of column dicts including `id`, `name`, `cohort`, `score`, `email`.

- [ ] **Step 3: Commit**

```powershell
git add implementation/db.py
git commit -m "feat(db): add SQLiteAdapter connection and schema inspection"
```

---

### Task 4: SQLite Adapter — `search`

**Files:**
- Modify: `implementation/db.py` (append `search` to `SQLiteAdapter`)

- [ ] **Step 1: Append `search` to `SQLiteAdapter`**

Insert at end of the class (before any module-level code):

```python
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

        # pagination
        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit must be a positive integer.")
        if limit > MAX_LIMIT:
            raise ValidationError(f"limit cannot exceed {MAX_LIMIT}.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a non-negative integer.")

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
```

- [ ] **Step 2: Smoke test in REPL**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter; a = SQLiteAdapter('implementation/lab.db'); import json; print(json.dumps(a.search('students', filters=[{'column':'cohort','op':'eq','value':'A1'}], order_by='score', descending=True, limit=10), indent=2))"
```

Expected: returns Alice (score 92.5) and Bao (78.0) in that order; `total_matching` = 2; `has_more` = False.

- [ ] **Step 3: Verify the failure paths**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter, ValidationError; a = SQLiteAdapter('implementation/lab.db'); 
try: a.search('nonexistent')
except ValidationError as e: print('OK:', e)"
```

Expected: `OK: Unknown table: 'nonexistent'`.

- [ ] **Step 4: Commit**

```powershell
git add implementation/db.py
git commit -m "feat(db): add validated search with filters, ordering, pagination"
```

---

### Task 5: SQLite Adapter — `insert`

**Files:**
- Modify: `implementation/db.py` (append `insert` to `SQLiteAdapter`)

- [ ] **Step 1: Append `insert`**

```python
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
```

- [ ] **Step 2: Smoke test**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter; a = SQLiteAdapter('implementation/lab.db'); import json; print(json.dumps(a.insert('students', {'name':'Test Tan','cohort':'B1','score':70.0,'email':'tan@example.com'}), indent=2))"
```

Expected: `inserted_id` is `6` (first insert) and `row` echoes the new student.

- [ ] **Step 3: Verify empty-insert rejection**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter, ValidationError; a = SQLiteAdapter('implementation/lab.db');
try: a.insert('students', {})
except ValidationError as e: print('OK:', e)"
```

Expected: `OK: values must be a non-empty mapping...`.

- [ ] **Step 4: Commit**

```powershell
git add implementation/db.py
git commit -m "feat(db): add validated insert with returned payload"
```

---

### Task 6: SQLite Adapter — `aggregate`

**Files:**
- Modify: `implementation/db.py` (append `aggregate` to `SQLiteAdapter`)

- [ ] **Step 1: Append `aggregate`**

```python
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
            metric_expr = "COUNT(*)" if column is None else f"COUNT({column})"
            if column is not None:
                self._validate_columns(table, [column])
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
```

- [ ] **Step 2: Smoke test (all five metrics + group_by)**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter; a = SQLiteAdapter('implementation/lab.db'); import json; 
print(json.dumps(a.aggregate('students','count'), indent=2)); 
print(json.dumps(a.aggregate('students','avg','score', group_by='cohort'), indent=2));
print(json.dumps(a.aggregate('students','max','score'), indent=2))"
```

Expected: `count` returns one row with `value` = total students; `avg` grouped by cohort returns one row per cohort; `max` returns 92.5 (Alice).

- [ ] **Step 3: Verify metric rejection**

```powershell
py -3.11 -c "from implementation.db import SQLiteAdapter, ValidationError; a = SQLiteAdapter('implementation/lab.db');
try: a.aggregate('students','median','score')
except ValidationError as e: print('OK:', e)"
```

Expected: `OK: Unsupported metric 'median'...`.

- [ ] **Step 4: Commit**

```powershell
git add implementation/db.py
git commit -m "feat(db): add validated aggregate with count/sum/avg/min/max + group_by"
```

---

### Task 7: FastMCP Server — Tools

**Files:**
- Create: `implementation/mcp_server.py`

- [ ] **Step 1: Write `implementation/mcp_server.py`**

```python
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
create_database(DB_PATH)
adapter = SQLiteAdapter(DB_PATH)

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
        "filters is a list of {column, op, value}. Supported ops: "
        "eq, ne, lt, lte, gt, gte, like, in, is_null."
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
    return _safe(lambda: adapter.search(
        table,
        columns=columns,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        descending=descending,
    ))


@mcp.tool(
    name="insert",
    description="Insert a row into a table. values is a {column: value} mapping; returns the inserted row.",
)
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    return _safe(lambda: adapter.insert(table, values))


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
    return _safe(lambda: adapter.aggregate(
        table,
        metric=metric,
        column=column,
        filters=filters,
        group_by=group_by,
    ))


# Resources are added in Task 8.


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
```

(`from db import ...` works because the server runs from `implementation/`; the Inspector/Claude/Codex/Gemini configs all set CWD or path accordingly.)

- [ ] **Step 2: Manual run smoke test — stdio**

```powershell
py -3.11 implementation/mcp_server.py
```

Expected: process starts and waits on stdin (no errors). Kill with Ctrl+C.

- [ ] **Step 3: Commit**

```powershell
git add implementation/mcp_server.py
git commit -m "feat(server): expose search/insert/aggregate as FastMCP tools"
```

---

### Task 8: FastMCP Server — Resources

**Files:**
- Modify: `implementation/mcp_server.py` (append resources before the `_main` block)

- [ ] **Step 1: Insert resource handlers**

Add immediately above `def _main()`:

```python
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
```

- [ ] **Step 2: Smoke test resource registration via Python**

```powershell
py -3.11 -c "import asyncio, json; from fastmcp import Client; 
async def main():
    async with Client('implementation/mcp_server.py') as c:
        resources = await c.list_resources()
        templates = await c.list_resource_templates()
        print('resources:', [r.uri for r in resources])
        print('templates:', [t.uriTemplate for t in templates])
asyncio.run(main())"
```

Expected: `resources: ['schema://database']`, `templates: ['schema://table/{table_name}']`.

- [ ] **Step 3: Commit**

```powershell
git add implementation/mcp_server.py
git commit -m "feat(server): expose database and per-table schema as MCP resources"
```

---

### Task 9: Automated Tests (`pytest`)

**Files:**
- Create: `implementation/tests/conftest.py`
- Create: `implementation/tests/test_db.py`
- Create: `implementation/tests/test_server.py`

- [ ] **Step 1: Write `conftest.py`**

```python
"""Shared fixtures: each test gets a fresh, isolated SQLite DB."""
from __future__ import annotations

import os
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
```

- [ ] **Step 2: Write `test_db.py`**

```python
import pytest

from db import SQLiteAdapter, ValidationError


def test_list_tables_includes_seeded(adapter: SQLiteAdapter):
    assert set(adapter.list_tables()) >= {"students", "courses", "enrollments"}


def test_search_filter_order_limit(adapter: SQLiteAdapter):
    res = adapter.search(
        "students",
        filters=[{"column": "cohort", "op": "eq", "value": "A1"}],
        order_by="score",
        descending=True,
        limit=10,
    )
    assert res["count"] == 2
    assert res["rows"][0]["name"] == "Alice Nguyen"
    assert res["total_matching"] == 2
    assert res["has_more"] is False


def test_search_pagination_has_more(adapter: SQLiteAdapter):
    page1 = adapter.search("students", limit=2, offset=0, order_by="id")
    page2 = adapter.search("students", limit=2, offset=2, order_by="id")
    assert page1["has_more"] is True
    assert page1["rows"][0]["id"] == 1
    assert page2["rows"][0]["id"] == 3


def test_search_rejects_unknown_table(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unknown table"):
        adapter.search("missing")


def test_search_rejects_unknown_column(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.search("students", columns=["nope"])


def test_search_rejects_bad_operator(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unsupported operator"):
        adapter.search(
            "students",
            filters=[{"column": "cohort", "op": "approx", "value": "A1"}],
        )


def test_insert_returns_payload(adapter: SQLiteAdapter):
    res = adapter.insert(
        "students",
        {"name": "Zed", "cohort": "C1", "score": 70.0, "email": "zed@example.com"},
    )
    assert res["inserted_id"] >= 1
    assert res["row"]["name"] == "Zed"


def test_insert_rejects_empty(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="non-empty mapping"):
        adapter.insert("students", {})


def test_insert_rejects_bad_column(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.insert("students", {"nope": 1})


def test_aggregate_count(adapter: SQLiteAdapter):
    res = adapter.aggregate("students", "count")
    assert res["rows"][0]["value"] == 5


def test_aggregate_avg_grouped(adapter: SQLiteAdapter):
    res = adapter.aggregate("students", "avg", column="score", group_by="cohort")
    cohorts = {row["cohort"]: row["value"] for row in res["rows"]}
    assert set(cohorts) == {"A1", "A2", "B1"}


def test_aggregate_rejects_metric(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="Unsupported metric"):
        adapter.aggregate("students", "median", column="score")


def test_aggregate_requires_column_for_avg(adapter: SQLiteAdapter):
    with pytest.raises(ValidationError, match="requires a 'column'"):
        adapter.aggregate("students", "avg")
```

- [ ] **Step 3: Write `test_server.py`**

```python
"""Integration tests using FastMCP's in-memory client transport."""
import asyncio
import json

import pytest
from fastmcp import Client


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_tools_are_discoverable(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            tools = await c.list_tools()
            return {t.name for t in tools}
    assert _run(go()) == {"search", "insert", "aggregate"}


def test_resource_and_template_are_discoverable(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            resources = [r.uri for r in await c.list_resources()]
            templates = [t.uriTemplate for t in await c.list_resource_templates()]
            return resources, templates
    resources, templates = _run(go())
    assert "schema://database" in [str(r) for r in resources]
    assert "schema://table/{table_name}" in templates


def test_search_tool_call_success(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.call_tool(
                "search",
                {"table": "students",
                 "filters": [{"column": "cohort", "op": "eq", "value": "A1"}]},
            )
    result = _run(go())
    payload = result.structured_content or json.loads(result.content[0].text)
    assert payload["count"] == 2


def test_insert_then_search_roundtrip(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            await c.call_tool(
                "insert",
                {"table": "students",
                 "values": {"name": "Roundtrip", "cohort": "C1", "score": 50,
                            "email": "rt@example.com"}},
            )
            return await c.call_tool(
                "search",
                {"table": "students",
                 "filters": [{"column": "name", "op": "eq", "value": "Roundtrip"}]},
            )
    result = _run(go())
    payload = result.structured_content or json.loads(result.content[0].text)
    assert payload["count"] == 1


def test_invalid_table_returns_error(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.call_tool("search", {"table": "nonexistent"})
    result = _run(go())
    assert result.is_error
    text = (result.content[0].text if result.content else "").lower()
    assert "unknown table" in text


def test_read_schema_resource(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.read_resource("schema://database")
    contents = _run(go())
    payload = json.loads(contents[0].text)
    assert "students" in payload["tables"]


def test_read_table_schema_template(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.read_resource("schema://table/students")
    contents = _run(go())
    payload = json.loads(contents[0].text)
    assert payload["table"] == "students"
    assert any(col["name"] == "cohort" for col in payload["columns"])
```

- [ ] **Step 4: Run the test suite**

```powershell
py -3.11 -m pytest implementation/tests -v
```

Expected: all tests pass (≥ 17 assertions across `test_db.py` + `test_server.py`).

- [ ] **Step 5: Commit**

```powershell
git add implementation/tests
git commit -m "test: add unit + integration coverage for adapter, tools, and resources"
```

---

### Task 10: `verify_server.py` Smoke Script

**Files:**
- Create: `implementation/verify_server.py`

- [ ] **Step 1: Write the script**

```python
"""End-to-end verification: discovery + success + failure, printed for the grader.

Run from the repository root with:

    py -3.11 implementation/verify_server.py
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastmcp import Client

SERVER_SCRIPT = Path(__file__).with_name("mcp_server.py")


def _ok(label: str, value) -> None:
    print(f"[OK] {label}: {value}")


def _fail_seen(label: str, err: str) -> None:
    print(f"[OK] {label}: error surfaced -> {err.splitlines()[0]}")


async def main() -> None:
    async with Client(str(SERVER_SCRIPT)) as c:
        tools = await c.list_tools()
        _ok("tool discovery", sorted(t.name for t in tools))

        resources = await c.list_resources()
        templates = await c.list_resource_templates()
        _ok("resource discovery", [str(r.uri) for r in resources])
        _ok("template discovery", [t.uriTemplate for t in templates])

        # successful search
        r = await c.call_tool(
            "search",
            {"table": "students",
             "order_by": "score", "descending": True, "limit": 3},
        )
        payload = r.structured_content or json.loads(r.content[0].text)
        _ok("search top-3 by score", [row["name"] for row in payload["rows"]])

        # aggregate
        r = await c.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg",
             "column": "score", "group_by": "cohort"},
        )
        payload = r.structured_content or json.loads(r.content[0].text)
        _ok("avg score per cohort", payload["rows"])

        # insert
        r = await c.call_tool(
            "insert",
            {"table": "courses",
             "values": {"code": "DEMO", "title": "Demo Course", "credits": 1}},
        )
        payload = r.structured_content or json.loads(r.content[0].text)
        _ok("insert course", payload["row"])

        # resource read
        c1 = await c.read_resource("schema://database")
        _ok("schema://database tables",
            list(json.loads(c1[0].text)["tables"].keys()))

        c2 = await c.read_resource("schema://table/students")
        _ok("schema://table/students columns",
            [col["name"] for col in json.loads(c2[0].text)["columns"]])

        # failing tool calls
        r = await c.call_tool("search", {"table": "ghost"})
        _fail_seen("unknown table", r.content[0].text)

        r = await c.call_tool(
            "aggregate",
            {"table": "students", "metric": "median", "column": "score"},
        )
        _fail_seen("unsupported metric", r.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it**

```powershell
py -3.11 implementation/verify_server.py
```

Expected: a clean sequence of `[OK]` lines covering discovery, three successful tool calls, two resource reads, and two intentional failures.

- [ ] **Step 3: Commit**

```powershell
git add implementation/verify_server.py
git commit -m "feat(verify): add end-to-end smoke script for grader"
```

---

### Task 11: Inspector & Client Configuration Files

**Files:**
- Create: `implementation/start_inspector.ps1`
- Create: `implementation/start_inspector.sh`
- Create: `implementation/.mcp.json.example`
- Create: `implementation/codex_config.example.toml`
- Create: `implementation/gemini_settings.example.json`

- [ ] **Step 1: Write `start_inspector.ps1`**

```powershell
# Launches MCP Inspector against the local FastMCP server.
# Usage:  ./implementation/start_inspector.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source
$cache  = Join-Path $root ".npm-cache"
New-Item -ItemType Directory -Force $cache | Out-Null
$env:NPM_CONFIG_CACHE = $cache
npx -y "@modelcontextprotocol/inspector" $python (Join-Path $root "mcp_server.py")
```

- [ ] **Step 2: Write `start_inspector.sh`**

```bash
#!/usr/bin/env bash
# Launches MCP Inspector against the local FastMCP server.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$(command -v python)}"
mkdir -p "$ROOT/.npm-cache"
NPM_CONFIG_CACHE="$ROOT/.npm-cache" \
  npx -y @modelcontextprotocol/inspector "$PYTHON" "$ROOT/mcp_server.py"
```

Mark executable when on a Unix host: `chmod +x implementation/start_inspector.sh` (skip on Windows).

- [ ] **Step 3: Write `.mcp.json.example`**

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "REPLACE_WITH_ABSOLUTE_PYTHON_PATH",
      "args": ["REPLACE_WITH_ABSOLUTE_PATH/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

- [ ] **Step 4: Write `codex_config.example.toml`**

```toml
[mcp_servers.sqlite_lab]
command = "REPLACE_WITH_ABSOLUTE_PYTHON_PATH"
args = ["REPLACE_WITH_ABSOLUTE_PATH/implementation/mcp_server.py"]
```

- [ ] **Step 5: Write `gemini_settings.example.json`**

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "command": "REPLACE_WITH_ABSOLUTE_PYTHON_PATH",
      "args": ["REPLACE_WITH_ABSOLUTE_PATH/implementation/mcp_server.py"],
      "cwd": "REPLACE_WITH_ABSOLUTE_PATH/implementation",
      "timeout": 10000,
      "trust": false
    }
  }
}
```

- [ ] **Step 6: Commit**

```powershell
git add implementation/start_inspector.ps1 implementation/start_inspector.sh implementation/.mcp.json.example implementation/codex_config.example.toml implementation/gemini_settings.example.json
git commit -m "chore: add Inspector helpers and client config examples"
```

---

### Task 12: Connect One Real MCP Client

Pick **one** client to verify end-to-end. Gemini CLI is fastest if installed; otherwise Claude Code (already running this session).

- [ ] **Step 1 — Option A: Gemini CLI**

```powershell
gemini mcp add sqlite-lab (Get-Command python).Source "$PWD/implementation/mcp_server.py" --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

Expected: `sqlite-lab` shown as `Connected`. Then:

```powershell
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server to show me the top 2 students by score."
```

Expected: a response that mentions Alice Nguyen and Eric Vo (or similar top scorers depending on inserts).

- [ ] **Step 1 — Option B: Claude Code**

Copy `implementation/.mcp.json.example` to `.mcp.json` at repo root, replace the absolute paths, then in Claude Code run `/mcp` and confirm `sqlite-lab` is connected. Reference `@sqlite-lab:schema://database` in a prompt and verify it returns the JSON snapshot.

- [ ] **Step 2: Capture evidence**

Take a screenshot (Inspector or the chosen client) showing the tools list and one successful call. Save under `docs/screenshots/` (create the folder). Reference it in the README in Task 13.

- [ ] **Step 3: Commit (only if new files were added — screenshots)**

```powershell
git add docs/screenshots
git commit -m "docs: add client integration screenshots"
```

---

### Task 13: README + Demo Script

**Files:**
- Modify: `README.md` (add Setup / Run / Verify / Client / Demo sections at the bottom)
- Create: `DEMO.md`

- [ ] **Step 1: Append to `README.md`**

Append this section verbatim *after* the existing content, so the original lab spec is preserved:

```markdown
---

## Implementation: Setup & Run

### 1. Install

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r implementation/requirements.txt
```

### 2. Initialize the database

```powershell
py -3.11 implementation/init_db.py
```

Creates `implementation/lab.db` with `students`, `courses`, `enrollments` tables and seed rows.

### 3. Run the FastMCP server (stdio)

```powershell
py -3.11 implementation/mcp_server.py
```

### 4. Verify end-to-end

```powershell
py -3.11 implementation/verify_server.py
py -3.11 -m pytest implementation/tests -v
```

`verify_server.py` exercises tool discovery, three successful tool calls, two resource reads, and two intentional error paths. `pytest` adds isolated DB-per-test coverage.

### 5. Inspect

```powershell
./implementation/start_inspector.ps1
```

(Or `./implementation/start_inspector.sh` on macOS/Linux.) See `docs/screenshots/` for reference output.

## Implementation: Tool Reference

### `search(table, columns?, filters?, limit=20, offset=0, order_by?, descending=false)`

- `filters`: list of `{column, op, value}`. Supported `op`s: `eq, ne, lt, lte, gt, gte, like, in, is_null`.
- Returns `{table, rows, count, total_matching, limit, offset, has_more}`.

### `insert(table, values)`

- `values`: non-empty `{column: value}` mapping.
- Returns `{table, inserted_id, row}`.

### `aggregate(table, metric, column?, filters?, group_by?)`

- `metric`: `count | sum | avg | min | max`. All metrics except `count` require `column`.
- Returns `{table, metric, column, group_by, rows}`.

## Implementation: Resources

- `schema://database` — full JSON snapshot of every non-internal table.
- `schema://table/{table_name}` — schema for a single table.

## Implementation: Client Configuration

Edit one of these examples, replacing `REPLACE_WITH_ABSOLUTE_*` placeholders:

- Claude Code: `implementation/.mcp.json.example` → copy to `.mcp.json` at repo root.
- Codex: `implementation/codex_config.example.toml` → merge into `~/.codex/config.toml`.
- Gemini CLI: prefer `gemini mcp add sqlite-lab <python> <abs path>/implementation/mcp_server.py --timeout 10000`.

## Implementation: Demo

See [DEMO.md](DEMO.md) for the 2-minute video script.
```

- [ ] **Step 2: Write `DEMO.md`**

```markdown
# 2-Minute Demo Script

Total runtime: ~2 minutes. Record screen + voice.

| Time | Show | Say |
|---|---|---|
| 0:00 | Terminal at repo root, `tree implementation/` output | "This is a FastMCP server that exposes a SQLite database through three tools and two schema resources." |
| 0:15 | Run `py -3.11 implementation/init_db.py` | "First we initialize a small relational database — students, courses, enrollments." |
| 0:25 | Run `./implementation/start_inspector.ps1` and open Inspector | "MCP Inspector connects via stdio and discovers the tools and resources." |
| 0:45 | Inspector → Tools tab → call `search` with `{"table":"students","filters":[{"column":"cohort","op":"eq","value":"A1"}]}` | "search supports filters, ordering, and pagination." |
| 1:05 | Inspector → Tools tab → call `insert` with a new student | "insert validates columns and returns the new row plus the generated id." |
| 1:20 | Inspector → Tools tab → call `aggregate` `{"table":"students","metric":"avg","column":"score","group_by":"cohort"}` | "aggregate covers count, sum, avg, min, max — with optional group_by." |
| 1:35 | Inspector → Resources tab → read `schema://database` and `schema://table/students` | "The schema is exposed as MCP resources, so the model can ground its queries." |
| 1:45 | Inspector → call `search` with `{"table":"ghost"}` and show the error | "Invalid input is rejected before we touch SQL." |
| 1:55 | Switch to Gemini CLI / Claude Code window with `gemini mcp list` showing Connected | "Same server, connected to a real client end-to-end." |
```

- [ ] **Step 3: Commit**

```powershell
git add README.md DEMO.md
git commit -m "docs: add setup, tool reference, client config, and demo script"
```

---

### Task 14 (Bonus +5): HTTP Transport with Bearer Auth

**Files:**
- Modify: `implementation/mcp_server.py` (extend `_main` and add `--auth-token` flag)
- Modify: `README.md` (document the optional HTTP mode)

- [ ] **Step 1: Replace `_main` with the auth-aware version**

```python
def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("MCP_AUTH_TOKEN"),
        help="Required bearer token for http/sse transports. Reads MCP_AUTH_TOKEN env var by default.",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
        return

    if not args.auth_token:
        raise SystemExit("--auth-token (or MCP_AUTH_TOKEN) is required for http/sse transports.")

    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class BearerAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            header = request.headers.get("authorization", "")
            if header != f"Bearer {args.auth_token}":
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    mcp.run(
        transport=args.transport,
        host=args.host,
        port=args.port,
        middleware=[Middleware(BearerAuth)],
    )
```

- [ ] **Step 2: Smoke test**

```powershell
$env:MCP_AUTH_TOKEN = "dev-token"
py -3.11 implementation/mcp_server.py --transport http --port 8765 &
Start-Sleep -Seconds 2
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8765/mcp/
curl.exe -s -o NUL -w "%{http_code}`n" -H "Authorization: Bearer dev-token" http://127.0.0.1:8765/mcp/
```

Expected: first call returns `401`, second returns `200` (or another non-401 success-class code depending on FastMCP's HTTP path). Then stop the background job.

- [ ] **Step 3: Document and commit**

Add a short section under "Implementation: Setup & Run" in `README.md`:

```markdown
### Optional: HTTP transport with bearer auth

```powershell
$env:MCP_AUTH_TOKEN = "dev-token"
py -3.11 implementation/mcp_server.py --transport http --port 8765
```

Requests without `Authorization: Bearer dev-token` receive `401 Unauthorized`.
```

Commit:

```powershell
git add implementation/mcp_server.py README.md
git commit -m "feat(server): add HTTP transport with bearer-token auth (bonus)"
```

---

### Task 15 (Bonus +3): PostgreSQL Adapter

**Files:**
- Create: `implementation/pg.py`
- Modify: `implementation/mcp_server.py` (pick adapter from `LAB_BACKEND` env)
- Create: `implementation/tests/test_pg.py` (skipped unless `LAB_PG_URL` is set)

- [ ] **Step 1: Write `implementation/pg.py`**

```python
"""PostgreSQL adapter mirroring SQLiteAdapter's surface.

Optional dependency: ``psycopg``. Only imported when this module is used.
"""
from __future__ import annotations

from typing import Any, Iterable

from db import SUPPORTED_METRICS, SUPPORTED_OPERATORS, MAX_LIMIT, ValidationError


class PostgresAdapter:
    def __init__(self, dsn: str):
        import psycopg  # local import: optional dependency
        self._psycopg = psycopg
        self.dsn = dsn

    def _connect(self):
        return self._psycopg.connect(self.dsn, row_factory=self._psycopg.rows.dict_row)

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

    # validation + search/insert/aggregate mirror SQLiteAdapter but use %s placeholders.
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

    def search(self, table, columns=None, filters=None, limit=20, offset=0,
               order_by=None, descending=False):
        self._validate_table(table)
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
        if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            raise ValidationError(f"limit must be 1..{MAX_LIMIT}.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be >= 0.")
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
            metric_expr = "COUNT(*)" if column is None else f"COUNT({column})"
            if column is not None:
                self._validate_columns(table, [column])
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
```

- [ ] **Step 2: Switch adapter in `mcp_server.py` based on env**

Replace the `create_database` + `adapter = SQLiteAdapter(...)` lines with:

```python
backend = os.environ.get("LAB_BACKEND", "sqlite").lower()
if backend == "postgres":
    from pg import PostgresAdapter
    adapter = PostgresAdapter(os.environ["LAB_PG_URL"])
else:
    create_database(DB_PATH)
    adapter = SQLiteAdapter(DB_PATH)
```

- [ ] **Step 3: Write a Postgres-conditional smoke test**

`implementation/tests/test_pg.py`:

```python
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("LAB_PG_URL"),
    reason="LAB_PG_URL not set; skipping Postgres adapter test.",
)


def test_pg_adapter_lists_tables():
    from pg import PostgresAdapter
    a = PostgresAdapter(os.environ["LAB_PG_URL"])
    assert isinstance(a.list_tables(), list)
```

- [ ] **Step 4: Run the suite and confirm Postgres test is skipped (or runs if you provide a URL)**

```powershell
py -3.11 -m pytest implementation/tests -v
```

Expected: `test_pg_adapter_lists_tables` shows as SKIPPED unless `LAB_PG_URL` is exported.

- [ ] **Step 5: Commit**

```powershell
git add implementation/pg.py implementation/mcp_server.py implementation/tests/test_pg.py
git commit -m "feat: add optional Postgres adapter behind shared interface (bonus)"
```

---

### Task 16 (Bonus +2): Output Caps, Pagination Hints, Structured Test Polish

**Files:**
- Modify: `implementation/mcp_server.py` (truncate giant payloads, add pagination note in tool description)
- Modify: `README.md` (Tool Reference section: document the cap)

- [ ] **Step 1: Add `_with_output_hints` helper at the top of `mcp_server.py` (above the tools)**

```python
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
        payload = {
            "table": payload.get("table"),
            "truncated": True,
            "hint": (
                "Response exceeded character budget. Reduce 'limit' "
                "or project fewer columns."
            ),
        }
    return payload
```

- [ ] **Step 2: Wrap each tool's return value**

In `search`, `insert`, `aggregate`, replace `return _safe(lambda: ...)` with:

```python
return _with_output_hints(_safe(lambda: adapter.<method>(...)))
```

(`<method>` = `search` / `insert` / `aggregate` as appropriate. `insert` will pass through unchanged in practice since it returns a single row, but the wrapper is harmless.)

- [ ] **Step 3: Update each tool's `description` string to mention pagination**

Example for `search`:

```python
description=(
    "Search rows in a table with optional filters, projection, ordering and pagination. "
    "filters is a list of {column, op, value}. Supported ops: eq, ne, lt, lte, gt, gte, "
    "like, in, is_null. Use limit (default 20, max 500) and offset for pagination — "
    "the response includes 'total_matching' and 'has_more'."
),
```

- [ ] **Step 4: Add a pagination test**

Append to `implementation/tests/test_server.py`:

```python
def test_search_response_includes_pagination_metadata(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.call_tool("search", {"table": "students", "limit": 2})
    result = _run(go())
    payload = result.structured_content or json.loads(result.content[0].text)
    assert {"limit", "offset", "total_matching", "has_more"} <= payload.keys()
```

Run `pytest` and confirm all tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add implementation/mcp_server.py implementation/tests/test_server.py README.md
git commit -m "feat(server): add output cap and pagination hints (bonus polish)"
```

---

## Final Self-Review Checklist (run after every task is complete)

Run all of these from the repo root, in order. Each must pass before declaring victory.

1. `py -3.11 -m pytest implementation/tests -v` → 17+ tests pass, Postgres test skipped unless configured.
2. `py -3.11 implementation/verify_server.py` → prints `[OK]` for every line.
3. `./implementation/start_inspector.ps1` → Inspector connects; tool & resource lists populate.
4. Real client (Gemini CLI **or** Claude Code) lists `sqlite-lab` as Connected and successfully answers a question that requires the database.
5. `git log --oneline` shows a clean, sequential commit history matching the task breakdown.
6. `README.md` documents Setup, Tool Reference, Resources, Client Configuration, and Demo.
7. `DEMO.md` exists and matches the 2-minute video.

When every item above is green, the submission is ready.

---

## Spec Coverage Map (sanity)

| README requirement | Task(s) |
|---|---|
| FastMCP server with `search`, `insert`, `aggregate` | 7 |
| SQLite database layer, swappable | 3, 4, 5, 6, 15 |
| `schema://database` and `schema://table/{name}` resources | 8 |
| Reject unknown tables / columns / operators / metrics / empty inserts | 3, 4, 5, 6 |
| Parameterized SQL | 4, 5, 6 |
| Server starts; tools/resources discoverable | 7, 8, 10 |
| Success + failure tool calls demonstrated | 9, 10 |
| At least one MCP client connected | 12 |
| GitHub repo + setup instructions + tool descriptions + testing steps + client config + demo | 13 (README, DEMO.md) |
| Inspector startup helper | 11 |
| Bonus: HTTP/SSE auth | 14 |
| Bonus: SQLite + Postgres behind one interface | 15 |
| Bonus: pagination guidance / output limits / structured testing | 16 |

---

## Plan complete

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-sqlite-fastmcp-lab.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
