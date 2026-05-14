# 2-Minute Demo Script

Total runtime: ~2 minutes. Record screen + voice.

| Time | Show | Say |
|---|---|---|
| 0:00 | Terminal at repo root, output of `ls implementation/` | "This is a FastMCP server that exposes a SQLite database through three tools and two schema resources." |
| 0:15 | Run `.\.venv\Scripts\python.exe implementation\init_db.py` | "First we initialize a small relational database — students, courses, enrollments — with seed data." |
| 0:25 | Run `./implementation/start_inspector.ps1` (or `.sh`), wait for Inspector to open in the browser | "MCP Inspector connects via stdio and discovers the tools and resources." |
| 0:45 | Inspector → Tools tab → call `search` with `{"table":"students","filters":[{"column":"cohort","op":"eq","value":"A1"}]}` | "search supports filters, projection, ordering, and pagination." |
| 1:05 | Inspector → Tools tab → call `insert` with `{"table":"students","values":{"name":"Demo","cohort":"C1","score":80,"email":"demo@example.com"}}` | "insert validates columns and returns the new row plus the generated id." |
| 1:20 | Inspector → Tools tab → call `aggregate` `{"table":"students","metric":"avg","column":"score","group_by":"cohort"}` | "aggregate covers count, sum, avg, min, max — with optional group_by." |
| 1:35 | Inspector → Resources tab → read `schema://database` then `schema://table/students` | "The schema is exposed as MCP resources, so a model can ground its queries." |
| 1:45 | Inspector → call `search` with `{"table":"ghost"}` and show the resulting error | "Invalid input is rejected before we touch SQL." |
| 1:55 | Switch to Claude Code (or `gemini mcp list`) showing sqlite-lab as Connected | "Same server, connected to a real MCP client end-to-end." |

## Backup demo via verify_server.py

If Inspector is unavailable, the same evidence can be shown by running:

```
.\.venv\Scripts\python.exe implementation\verify_server.py
```

This prints ten `[OK]` lines covering discovery, three successful tool calls, two resource reads, and two intentional error paths.
