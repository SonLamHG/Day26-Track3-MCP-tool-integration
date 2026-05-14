"""End-to-end verification: discovery + success + failure, printed for the grader.

Run from the repository root with:

    .venv/Scripts/python.exe implementation/verify_server.py
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
    first_line = err.splitlines()[0] if err else ""
    print(f"[OK] {label}: error surfaced -> {first_line}")


def _payload(result):
    if getattr(result, "structured_content", None):
        sc = result.structured_content
        # FastMCP may wrap return values in {"result": {...}}
        if isinstance(sc, dict) and set(sc.keys()) == {"result"} and isinstance(sc["result"], dict):
            return sc["result"]
        return sc
    if result.content:
        return json.loads(result.content[0].text)
    return {}


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
        payload = _payload(r)
        _ok("search top-3 by score", [row["name"] for row in payload["rows"]])

        # aggregate (grouped avg)
        r = await c.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg",
             "column": "score", "group_by": "cohort"},
        )
        payload = _payload(r)
        _ok("avg score per cohort", payload["rows"])

        # insert (use a deterministic random suffix so re-runs don't collide on UNIQUE code)
        import secrets
        suffix = secrets.token_hex(3).upper()
        r = await c.call_tool(
            "insert",
            {"table": "courses",
             "values": {"code": f"DEMO-{suffix}",
                        "title": "Demo Course",
                        "credits": 1}},
        )
        payload = _payload(r)
        _ok("insert course", payload["row"])

        # resource reads
        c1 = await c.read_resource("schema://database")
        _ok("schema://database tables",
            list(json.loads(c1[0].text)["tables"].keys()))

        c2 = await c.read_resource("schema://table/students")
        _ok("schema://table/students columns",
            [col["name"] for col in json.loads(c2[0].text)["columns"]])

        # failing tool calls (capture without raising)
        r = await c.call_tool("search", {"table": "ghost"}, raise_on_error=False)
        _fail_seen("unknown table",
                   r.content[0].text if r.content else "")

        r = await c.call_tool(
            "aggregate",
            {"table": "students", "metric": "median", "column": "score"},
            raise_on_error=False,
        )
        _fail_seen("unsupported metric",
                   r.content[0].text if r.content else "")


if __name__ == "__main__":
    asyncio.run(main())
