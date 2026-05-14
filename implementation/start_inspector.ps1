# Launches MCP Inspector against the local FastMCP server.
# Usage:  ./implementation/start_inspector.ps1
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$root   = Split-Path -Parent $here
$python = Join-Path $root ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python).Source
}
$cache  = Join-Path $here ".npm-cache"
New-Item -ItemType Directory -Force $cache | Out-Null
$env:NPM_CONFIG_CACHE = $cache
npx -y "@modelcontextprotocol/inspector" $python (Join-Path $here "mcp_server.py")
