#!/bin/bash
set -e

cd "$(dirname "$0")/backend" 2>/dev/null || true

echo "Installing dependencies..."
python3.11 -m pip install -r requirements.txt -q

echo "Starting MCP server on port 8765..."
python3.11 mcp_server.py &
MCP_PID=$!
echo "  MCP PID: $MCP_PID"

echo "Starting API server on port 8000..."
python3.11 -m uvicorn app:app --reload --port 8000 --env-file .env

# If uvicorn exits, kill the MCP server too
kill $MCP_PID 2>/dev/null || true
