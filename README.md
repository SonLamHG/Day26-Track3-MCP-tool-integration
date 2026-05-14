# Lab: Build a Database MCP Server with FastMCP and SQLite

## Goal

Build a Model Context Protocol (MCP) server using FastMCP that exposes a small database through:

- `search`
- `insert`
- `aggregate`

You must also expose the database schema as an MCP resource, test the server with Inspector or equivalent tooling, and show the server working from at least one MCP client.

## Learning Outcomes

By the end of this lab, students should be able to:

- explain what MCP tools and resources are
- build a FastMCP server in Python
- connect FastMCP to a SQLite database
- safely validate database requests before executing SQL
- expose dynamic schema context through `@mcp.resource(...)`
- test tool schemas, normal calls, and error responses
- connect the server to an MCP client such as Claude Code, Codex, or Gemini CLI

## Required Features

### Part 1: MCP Server

Implement a FastMCP server that exposes exactly these tool categories:

1. `search`
2. `insert`
3. `aggregate`

Your server may use SQLite for the main implementation. If you want to support PostgreSQL too, design the code so the database layer can be swapped later.

### Part 2: Resource

Expose database schema information as MCP resources:

- one resource for the full database schema
- one dynamic resource template for a single table schema

Suggested URIs:

- `schema://database`
- `schema://table/{table_name}`

### Part 3: Validation and Error Handling

Your tools must reject unsafe or invalid requests:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate requests
- empty inserts

Do not build SQL by blindly concatenating raw user input.

### Part 4: Testing and Verification

Verify all of the following:

1. the server starts correctly
2. the three tools are discoverable
3. the schema resource is discoverable
4. valid tool calls return useful results
5. invalid tool calls return clear errors
6. at least one MCP client can connect and use the server

### Part 5: Demo Deliverables

Prepare:

- GitHub repository
- setup instructions
- tool descriptions
- testing steps
- at least one client configuration example
- short demo video, around 2 minutes

Inspector screenshots are recommended if you use MCP Inspector.

## Suggested Project Structure

```text
implementation/
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  tests/
    test_server.py
```

## Recommended Data Model

Use a small relational dataset so `search`, `insert`, and `aggregate` are easy to demo. Example:

- `students`
- `courses`
- `enrollments`

## Example Tasks to Demonstrate

- search all students in cohort `A1`
- insert a new student
- count rows in a table
- compute average score by cohort
- read the full schema resource
- read `schema://table/students`
- show an invalid request, such as searching a missing table

## FastMCP and Inspector References

- FastMCP quickstart: https://gofastmcp.com/v2/getting-started/quickstart
- FastMCP resources: https://gofastmcp.com/v2/servers/resources
- MCP Inspector: https://modelcontextprotocol.io/docs/tools/inspector

## Client Setup Notes

### Claude Code

Anthropic documents local JSON config and `claude mcp add` flows here:

- https://code.claude.com/docs/en/mcp

Claude Code supports MCP resources via `@server:resource-uri` references and supports environment variable expansion in `.mcp.json`.

### Codex

OpenAI documents Codex MCP setup here:

- https://developers.openai.com/learn/docs-mcp

Codex supports MCP server configuration through the CLI and `~/.codex/config.toml`.

### Gemini CLI

Gemini CLI has a built-in MCP manager. In the verified local workflow, the simplest path is:

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

Gemini CLI also documents configuration details here:

- https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md

Expected outcome:

- the server appears as `Connected`
- Gemini can discover `search`, `insert`, and `aggregate`
- a headless smoke test works with `gemini --allowed-mcp-server-names sqlite-lab --yolo -p "..."`

### Antigravity

Antigravity commonly uses an `mcp_config.json` file with a shape similar to Gemini CLI. Verify the current product behavior in your installed version before grading against exact UI steps.

## Deliverable Checklist

- working FastMCP server
- SQLite database and seed data
- `search`, `insert`, `aggregate` tools
- schema resource and schema resource template
- verification steps
- automated tests or repeatable verification script
- client configuration example
- README with setup and demo steps
- Inspector startup command or helper script
- at least one verified Gemini CLI or Claude/Codex client test

## Bonus

Optional bonus:

- add authentication for SSE or HTTP transport
- support both SQLite and PostgreSQL with the same MCP surface
- add richer output annotations or pagination

---

## Implementation: Setup & Run

### 1. Install

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r implementation/requirements.txt
```

(`py -3.11` may be replaced with any Python 3.10+ interpreter — adjust the activate path on macOS/Linux to `.venv/bin/activate`.)

### 2. Initialize the database

```powershell
.\.venv\Scripts\python.exe implementation\init_db.py
```

Creates `implementation/lab.db` with `students`, `courses`, `enrollments` tables and seed rows. The script is idempotent — running it twice is safe.

### 3. Run the FastMCP server (stdio)

```powershell
.\.venv\Scripts\python.exe implementation\mcp_server.py
```

Stdio transport is the default. The server is ready when it stops printing initialization messages and starts waiting on stdin.

### 4. Verify end-to-end

```powershell
.\.venv\Scripts\python.exe implementation\verify_server.py
.\.venv\Scripts\python.exe -m pytest implementation\tests -v
```

`verify_server.py` exercises tool discovery, three successful tool calls, two resource reads, and two intentional error paths — printing a `[OK]` line for each. `pytest` runs the 20-test suite (13 adapter tests + 7 server tests) with an isolated tmp DB per test.

### 5. Inspect with MCP Inspector

```powershell
./implementation/start_inspector.ps1
```

(macOS/Linux: `./implementation/start_inspector.sh`.) Inspector opens a browser UI where you can see tool schemas, call them, and read resources.

### Optional: HTTP transport with bearer auth (bonus)

```powershell
$env:MCP_AUTH_TOKEN = "dev-token"
.\.venv\Scripts\python.exe implementation\mcp_server.py --transport http --port 8765
```

The server rejects any request that doesn't carry `Authorization: Bearer $MCP_AUTH_TOKEN` with HTTP 401. Set `LAB_BACKEND=postgres` and `LAB_PG_URL=postgres://...` to point the same MCP surface at PostgreSQL instead of SQLite (bonus).

## Implementation: Tool Reference

### `search(table, columns?, filters?, limit=20, offset=0, order_by?, descending=false)`

- `filters`: list of `{column, op, value}`. Supported `op`s: `eq, ne, lt, lte, gt, gte, like, in, is_null`. `is_null` takes no `value`; `in` takes a list.
- `limit` is capped at 500; `offset` must be non-negative.
- Returns `{table, rows, count, total_matching, limit, offset, has_more}`.

### `insert(table, values)`

- `values`: non-empty `{column: value}` mapping. Empty maps are rejected.
- Returns `{table, inserted_id, row}` where `row` is the freshly inserted record (including auto-generated `id`).

### `aggregate(table, metric, column?, filters?, group_by?)`

- `metric`: one of `count, sum, avg, min, max`. All except `count` require `column`.
- Optional `filters` (same shape as `search`) and `group_by`.
- Returns `{table, metric, column, group_by, rows}`.

## Implementation: Resources

- **`schema://database`** — full JSON snapshot of every non-internal table in the database.
- **`schema://table/{table_name}`** — schema for a single table, addressed by name (e.g. `schema://table/students`).

## Implementation: Client Configuration

Pick one of the examples in `implementation/` and replace the `REPLACE_WITH_ABSOLUTE_*` placeholders with the real paths on your machine:

- **Claude Code:** copy `implementation/.mcp.json.example` to `.mcp.json` at the repo root. A pre-filled `.mcp.json` is already present for the original author's environment — adjust paths as needed.
- **Codex:** merge `implementation/codex_config.example.toml` into `~/.codex/config.toml`.
- **Gemini CLI:** prefer `gemini mcp add sqlite-lab <python> <abs path>/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000`; or use `implementation/gemini_settings.example.json`.

After configuring, reload your client (Claude Code: `/mcp`; Gemini: `gemini mcp list`) to confirm `sqlite-lab` shows as Connected.

## Implementation: Demo

See [DEMO.md](DEMO.md) for the 2-minute video walkthrough script.