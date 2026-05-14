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
