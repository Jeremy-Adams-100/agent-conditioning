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
GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config" \
    git -C /opt/wolfram-bridge pull --ff-only origin main 2>/dev/null || true

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
# Workspace is scoped to wolfram-bridge/workspace/
cat > /home/explorer/.env << EOF
VM_AGENT_TOKEN=${VM_AGENT_TOKEN}
DATA_DIR=/home/explorer/data
WORKING_DIR=/opt/wolfram-bridge/workspace
WOLFRAM_PATH=/usr/local/bin/wolfram
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

# --- Write tier-specific config ---
CONFIG_SRC=/opt/agent-conditioning/agent/config.yaml
CONFIG_DST=/home/explorer/config.yaml
SCORE_SRC=/opt/agent-conditioning/agent/exploration-score.yaml
SCORE_DST=/home/explorer/exploration-score.yaml

cp "$CONFIG_SRC" "$CONFIG_DST" 2>/dev/null || true
cp "$SCORE_SRC" "$SCORE_DST" 2>/dev/null || true

# Point working_directory at the wolfram-bridge workspace
sed -i "s|^working_directory:.*|working_directory: /opt/wolfram-bridge/workspace|" "$CONFIG_DST"

if [ "$TIER" = "max" ]; then
    echo "[startup] Tier: max (opus, 1M context, 30s cooldown)"
    sed -i 's/^model:.*/model: opus/' "$CONFIG_DST"
    sed -i 's/^context_window:.*/context_window: 1000000/' "$CONFIG_DST"
    sed -i 's/cycle_cooldown_seconds:.*/cycle_cooldown_seconds: 30/' "$SCORE_DST"
else
    echo "[startup] Tier: free (sonnet, 200k context, 300s cooldown)"
    sed -i 's/^model:.*/model: sonnet/' "$CONFIG_DST"
    sed -i 's/^context_window:.*/context_window: 200000/' "$CONFIG_DST"
    sed -i 's/cycle_cooldown_seconds:.*/cycle_cooldown_seconds: 300/' "$SCORE_DST"
fi

chown explorer:explorer "$CONFIG_DST" "$SCORE_DST" 2>/dev/null || true

# --- Ensure working directories exist ---
mkdir -p /home/explorer/data /opt/wolfram-bridge/workspace
chown -R explorer:explorer /home/explorer/data /opt/wolfram-bridge/workspace

echo "[startup] Done."
