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
