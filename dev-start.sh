#!/bin/bash
# Start all three services for local development.
# Run from the agent-conditioning root directory.
#
# Usage: ./dev-start.sh
# Stop:  Ctrl+C (kills all three)

set -euo pipefail

# Resolve project root (where this script lives)
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║         Q.E.D. Development Server     ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Load env vars
export $(grep -v '^#' "$PROJECT_ROOT/platform/.env" | xargs) 2>/dev/null || true

# Ensure data directories exist
mkdir -p "$PROJECT_ROOT/agent/data" "$PROJECT_ROOT/agent/output" /tmp/qed-workspace

# 1. VM Agent (port 8080)
export VM_AGENT_TOKEN="dev-token-local"
export DATA_DIR="$PROJECT_ROOT/agent/data"
export WORKING_DIR="/data/home/jadams2/wolfram-bridge"
export INTERACT_WORKSPACE="$(dirname "$WORKING_DIR")/interact"
mkdir -p "$INTERACT_WORKSPACE"
export PYTHONPATH="$PROJECT_ROOT/platform"
export EXPLORATION_CMD="$PROJECT_ROOT/platform/.venv/bin/python -m agent.exploration --score $PROJECT_ROOT/agent/exploration-score.yaml --config $PROJECT_ROOT/agent/config.yaml --state $PROJECT_ROOT/agent/data/exploration_state.json"
export PROJECT_ROOT="$PROJECT_ROOT"

echo "  [1/3] VM agent on :8080..."
cd "$PROJECT_ROOT/platform" && uv run uvicorn vm_agent.agent:app --host 127.0.0.1 --port 8080 > /dev/null 2>&1 &
VM_PID=$!
sleep 1

# 2. Backend API (port 8000)
echo "  [2/3] Backend API on :8000..."
cd "$PROJECT_ROOT/platform" && uv run uvicorn explorer_platform.app:app --host 127.0.0.1 --port 8000 > /dev/null 2>&1 &
API_PID=$!
sleep 1

# 3. Frontend (port 3000)
echo "  [3/3] Frontend on :3000..."
cd "$PROJECT_ROOT/frontend" && npm run dev > /dev/null 2>&1 &
FE_PID=$!
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
