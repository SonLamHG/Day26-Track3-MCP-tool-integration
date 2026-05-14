#!/usr/bin/env bash
# Launches MCP Inspector against the local FastMCP server.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/Scripts/python.exe}"
if [ ! -x "$PYTHON" ]; then PYTHON="${PYTHON:-$(command -v python)}"; fi
mkdir -p "$HERE/.npm-cache"
NPM_CONFIG_CACHE="$HERE/.npm-cache" \
  npx -y @modelcontextprotocol/inspector "$PYTHON" "$HERE/mcp_server.py"
