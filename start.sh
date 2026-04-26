#!/bin/bash
# ADsensei — start backend + frontend
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ADsensei — AI Video Ad Personalisation"
echo "  ──────────────────────────────────────"
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶ Starting backend on http://localhost:8000"
cd "$ROOT/backend"
python3.11 -m pip install -r requirements.txt -q

# MCP server (port 8765) in background
python3.11 mcp_server.py > /tmp/mcp.log 2>&1 &
MCP_PID=$!
echo "  MCP server PID $MCP_PID → /tmp/mcp.log"

# API server in background
python3.11 -m uvicorn app:app --port 8000 --env-file .env > /tmp/backend.log 2>&1 &
API_PID=$!
echo "  API server PID $API_PID  → /tmp/backend.log"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ Starting frontend on http://localhost:3000"
cd "$ROOT/frontend"
npm run dev > /tmp/frontend.log 2>&1 &
FE_PID=$!
echo "  Frontend PID   $FE_PID  → /tmp/frontend.log"

# ── Ready ─────────────────────────────────────────────────────────────────────
echo ""
echo "  Waiting for servers to boot..."
sleep 5

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null)
FE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null)

echo ""
echo "  Backend  →  http://localhost:8000  [$HEALTH]"
echo "  Frontend →  http://localhost:3000  [$FE]"
echo "  MCP      →  http://localhost:8765/mcp"
echo "  Slides   →  $ROOT/slides.html"
echo ""
echo "  Demo login:  demo@test.com / demo1234"
echo ""
echo "  Logs:  tail -f /tmp/backend.log  /tmp/frontend.log  /tmp/mcp.log"
echo ""

# Keep script alive so Ctrl+C kills all children
trap "kill $MCP_PID $API_PID $FE_PID 2>/dev/null; echo 'Stopped.'; exit 0" INT TERM
wait $API_PID
