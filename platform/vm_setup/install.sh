#!/bin/bash
# Base image setup script for Agent Explorer VMs.
# Run once on the template VM, then snapshot.
set -euo pipefail

echo "=== Agent Explorer VM Setup ==="

# --- System packages ---
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git curl unzip

# --- Create explorer user ---
echo "[2/7] Creating explorer user..."
sudo useradd -m -s /bin/bash explorer || true
sudo mkdir -p /home/explorer/working /home/explorer/data
sudo chown -R explorer:explorer /home/explorer

# --- Install Claude Code CLI ---
echo "[3/7] Installing Claude Code CLI..."
# Claude Code installs via npm
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y -qq nodejs
sudo npm install -g @anthropic-ai/claude-code

# --- Install Wolfram Engine ---
echo "[4/7] Installing Wolfram Engine..."
# Download and install Wolfram Engine (free for personal use)
# The actual activation happens per-user at boot via startup script
if ! command -v wolfram &>/dev/null; then
    echo "NOTE: Wolfram Engine must be installed manually."
    echo "Download from: https://www.wolfram.com/engine/"
    echo "Install with: sudo dpkg -i WolframEngine_*.deb"
    echo "Skipping for now — install before snapshotting."
fi

# --- Install agent-conditioning + auto-compact ---
echo "[5/7] Installing agent-conditioning..."
sudo mkdir -p /opt/agent-conditioning /opt/auto-compact
# These will be copied from the dev machine before snapshotting
# For now, create the directory structure
sudo chown -R explorer:explorer /opt/agent-conditioning /opt/auto-compact

# --- Install VM agent dependencies ---
echo "[6/7] Installing Python dependencies..."
sudo -u explorer python3 -m venv /opt/agent-conditioning/.venv
sudo -u explorer /opt/agent-conditioning/.venv/bin/pip install -q \
    fastapi uvicorn[standard] httpx pyyaml bcrypt cryptography anthropic

# --- Install startup script ---
echo "[7/7] Installing startup script..."
sudo cp /tmp/vm-startup.sh /opt/vm-startup.sh
sudo chmod +x /opt/vm-startup.sh

# Create systemd service for the startup script
sudo tee /etc/systemd/system/explorer-setup.service > /dev/null << 'UNIT'
[Unit]
Description=Agent Explorer VM Setup
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/vm-startup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

# Create systemd service for the VM agent
sudo tee /etc/systemd/system/vm-agent.service > /dev/null << 'UNIT'
[Unit]
Description=Agent Explorer VM Agent
After=explorer-setup.service
Requires=explorer-setup.service

[Service]
Type=simple
User=explorer
WorkingDirectory=/opt/agent-conditioning
EnvironmentFile=/home/explorer/.env
ExecStart=/opt/agent-conditioning/.venv/bin/uvicorn vm_agent.agent:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable explorer-setup.service
sudo systemctl enable vm-agent.service

echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Install Wolfram Engine if not done"
echo "  2. Copy agent-conditioning + auto-compact code to /opt/"
echo "  3. Copy vm-startup.sh to /tmp/ and re-run step 7"
echo "  4. Test: sudo systemctl start explorer-setup && sudo systemctl start vm-agent"
echo "  5. Snapshot: gcloud compute images create agent-explorer-base-v1 --source-disk=agent-explorer-template --source-disk-zone=us-central1-a"
