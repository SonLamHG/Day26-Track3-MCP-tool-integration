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
