#!/bin/bash
# Per-boot startup script for Agent Explorer VMs.
# Reads user-specific credentials from GCP instance metadata
# and configures the VM for that user.
set -euo pipefail

METADATA_URL="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
METADATA_HEADER="Metadata-Flavor: Google"

# --- Pull latest code (read-only deploy keys) ---
echo "[startup] Pulling latest code..."
GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config" \
    git -C /opt/agent-conditioning pull --ff-only origin main 2>/dev/null || true
GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config" \
    git -C /opt/auto-compact pull --ff-only origin main 2>/dev/null || true

# --- Read instance metadata ---
echo "[startup] Reading instance metadata..."
VM_AGENT_TOKEN=$(curl -sf -H "$METADATA_HEADER" "$METADATA_URL/vm-agent-token" 2>/dev/null || echo "")
CLAUDE_TOKEN=$(curl -sf -H "$METADATA_HEADER" "$METADATA_URL/claude-token" 2>/dev/null || echo "")
WOLFRAM_KEY=$(curl -sf -H "$METADATA_HEADER" "$METADATA_URL/wolfram-key" 2>/dev/null || echo "")
TIER=$(curl -sf -H "$METADATA_HEADER" "$METADATA_URL/tier" 2>/dev/null || echo "unknown")

if [ -z "$VM_AGENT_TOKEN" ]; then
    echo "[startup] WARNING: No vm-agent-token in metadata."
fi

# --- Write environment file for VM agent ---
cat > /home/explorer/.env << EOF
VM_AGENT_TOKEN=${VM_AGENT_TOKEN}
DATA_DIR=/home/explorer/data
WORKING_DIR=/home/explorer/working
EOF
chown explorer:explorer /home/explorer/.env
chmod 600 /home/explorer/.env

# --- Configure Claude CLI (timeout 15s) ---
if [ -n "$CLAUDE_TOKEN" ]; then
    echo "[startup] Configuring Claude CLI..."
    timeout 15 sudo -u explorer bash -c "claude setup-token '$CLAUDE_TOKEN'" 2>/dev/null || \
        echo "[startup] WARNING: Claude setup-token failed or timed out"
fi

# --- Activate Wolfram Engine (timeout 30s) ---
if [ -n "$WOLFRAM_KEY" ]; then
    if ! timeout 10 sudo -u explorer wolfram -run "Print[1+1]" 2>/dev/null | grep -q "2"; then
        echo "[startup] Activating Wolfram Engine..."
        timeout 30 sudo -u explorer wolframscript -activate "$WOLFRAM_KEY" 2>/dev/null || \
            echo "[startup] WARNING: Wolfram activation failed or timed out"
    else
        echo "[startup] Wolfram Engine already activated."
    fi
fi

# --- Ensure working directories exist ---
mkdir -p /home/explorer/data /home/explorer/working
chown -R explorer:explorer /home/explorer/data /home/explorer/working

echo "[startup] Done."
