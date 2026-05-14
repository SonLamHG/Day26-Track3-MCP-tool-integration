"""Integration tests using FastMCP's in-memory client transport."""
import asyncio
import json

import pytest
from fastmcp import Client


def _run(coro):
    return asyncio.run(coro)


def _payload(result):
    """Extract structured payload from a CallToolResult."""
    if getattr(result, "structured_content", None):
        return result.structured_content
    if result.content:
        return json.loads(result.content[0].text)
    return None


def test_tools_are_discoverable(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            tools = await c.list_tools()
            return {t.name for t in tools}
    assert _run(go()) == {"search", "insert", "aggregate"}


def test_resource_and_template_are_discoverable(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            resources = [str(r.uri) for r in await c.list_resources()]
            templates = [t.uriTemplate for t in await c.list_resource_templates()]
            return resources, templates
    resources, templates = _run(go())
    assert "schema://database" in resources
    assert "schema://table/{table_name}" in templates


def test_search_tool_call_success(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.call_tool(
                "search",
                {"table": "students",
                 "filters": [{"column": "cohort", "op": "eq", "value": "A1"}]},
            )
    payload = _payload(_run(go()))
    # FastMCP may wrap the dict in a {"result": ...} envelope when structured_content is used.
    if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], dict):
        payload = payload["result"]
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
    payload = _payload(_run(go()))
    if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], dict):
        payload = payload["result"]
    assert payload["count"] == 1


def test_invalid_table_returns_error(server_module):
    async def go():
        async with Client(server_module.mcp) as c:
            return await c.call_tool("search", {"table": "nonexistent"}, raise_on_error=False)
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
