#!/bin/bash
# Start all three services for local development.
# Run from the agent-conditioning root directory.
#
# Usage: ./dev-start.sh
# Stop:  Ctrl+C (kills all three)

set -euo pipefail

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║         Q.E.D. Development Server     ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Load env vars
export $(grep -v '^#' platform/.env | xargs) 2>/dev/null || true

# Ensure data directories exist
mkdir -p agent/data agent/output /tmp/qed-workspace

# 1. VM Agent (port 8080)
export VM_AGENT_TOKEN="dev-token-local"
export DATA_DIR="$(pwd)/agent/data"
export WORKING_DIR="/tmp/qed-workspace"
export PYTHONPATH="$(pwd)/platform"

echo "  [1/3] VM agent on :8080..."
cd platform && uv run uvicorn vm_agent.agent:app --host 127.0.0.1 --port 8080 > /dev/null 2>&1 &
VM_PID=$!
cd ..
sleep 1

# 2. Backend API (port 8000)
echo "  [2/3] Backend API on :8000..."
cd platform && uv run uvicorn explorer_platform.app:app --host 127.0.0.1 --port 8000 > /dev/null 2>&1 &
API_PID=$!
cd ..
sleep 1

# 3. Frontend (port 3000)
echo "  [3/3] Frontend on :3000..."
cd frontend && npm run dev > /dev/null 2>&1 &
FE_PID=$!
cd ..
sleep 3

echo ""
echo "  ┌───────────────────────────────────────┐"
echo "  │                                       │"
echo "  │   Open:  http://localhost:3000         │"
echo "  │                                       │"
echo "  │   Press Ctrl+C to stop all services   │"
echo "  │                                       │"
echo "  └───────────────────────────────────────┘"
echo ""

# Wait for any to exit, then kill all
trap "echo ''; echo '  Shutting down...'; kill $VM_PID $API_PID $FE_PID 2>/dev/null; exit" INT TERM
wait
