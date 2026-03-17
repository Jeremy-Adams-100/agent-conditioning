#!/bin/bash
# Start all three services for local development.
# Run from the agent-conditioning root directory.
#
# Usage: ./dev-start.sh
# Stop:  Ctrl+C (kills all three)

set -euo pipefail

echo "=== Q.E.D. Development Server ==="
echo ""

# Load env vars
export $(grep -v '^#' platform/.env | xargs) 2>/dev/null || true

# Ensure data directories exist
mkdir -p agent/data agent/output /tmp/qed-workspace

# 1. VM Agent (port 8080) — handles exploration commands
export VM_AGENT_TOKEN="dev-token-local"
export DATA_DIR="$(pwd)/agent/data"
export WORKING_DIR="/tmp/qed-workspace"
export PYTHONPATH="$(pwd)/platform"

echo "[1/3] Starting VM agent on :8080..."
cd platform && uv run uvicorn vm_agent.agent:app --host 127.0.0.1 --port 8080 &
VM_PID=$!
cd ..

sleep 1

# 2. Backend API (port 8000) — handles auth, onboarding, proxies to VM agent
echo "[2/3] Starting backend API on :8000..."
cd platform && uv run uvicorn explorer_platform.app:app --host 127.0.0.1 --port 8000 &
API_PID=$!
cd ..

sleep 1

# 3. Frontend (port 3000) — Next.js dev server
echo "[3/3] Starting frontend on :3000..."
cd frontend && npm run dev &
FE_PID=$!
cd ..

echo ""
echo "=== All services running ==="
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  VM Agent:  http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# Wait for any to exit, then kill all
trap "kill $VM_PID $API_PID $FE_PID 2>/dev/null; exit" INT TERM
wait
