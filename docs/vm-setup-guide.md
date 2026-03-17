# VM Base Image Setup Guide

## Overview

Each user gets an isolated GCP Compute Engine VM cloned from a base
image. The base image contains all software pre-installed. Per-user
credentials are injected via GCP instance metadata at boot time.

## Current Base Image

| Field | Value |
|-------|-------|
| Name | `agent-explorer-base-v2` |
| Project | `agent-explorer-app` |
| Family | `agent-explorer` |
| OS | Ubuntu 24.04 LTS |
| Disk | 20GB SSD |
| Machine type | e2-medium (2 vCPU, 4GB RAM) |
| Status | READY |

## What's Installed

| Component | Location | Version |
|-----------|----------|---------|
| Claude Code CLI | `/usr/lib/node_modules/@anthropic-ai/claude-code/` | 2.1.77 |
| Node.js | `/usr/bin/node` | 22.x |
| Python 3.12 | `/usr/bin/python3` | System |
| Python venv | `/opt/agent-conditioning/.venv/` | With all deps |
| agent-conditioning | `/opt/agent-conditioning/` | Git clone (main) |
| auto-compact | `/opt/auto-compact/` | Git clone (main) |
| VM agent | `/opt/agent-conditioning/platform/vm_agent/` | Part of repo |
| Deploy keys | `/opt/deploy-keys/` | Read-only SSH keys |
| Startup script | `/opt/vm-startup.sh` | Runs on every boot |
| Wolfram Engine | **NOT INSTALLED** | Requires manual .deb download |

## Deploy Keys

Two read-only SSH deploy keys enable VMs to pull latest code on boot:

| Key | GitHub Repo | Name on GitHub |
|-----|-------------|----------------|
| `/opt/deploy-keys/deploy_key_agent_conditioning` | Jeremy-Adams-100/agent-conditioning | Agent Conditioning VM (read-only) |
| `/opt/deploy-keys/deploy_key_auto_compact` | Jeremy-Adams-100/auto-compact | Auto Compact VM (read-only) |

SSH config at `/opt/deploy-keys/ssh_config` maps host aliases to keys:
- `github-agent-conditioning` → uses agent-conditioning deploy key
- `github-auto-compact` → uses auto-compact deploy key

## Systemd Services

### explorer-setup.service (oneshot, runs on boot)

Runs `/opt/vm-startup.sh` which:
1. Pulls latest code via deploy keys (`git pull --ff-only`)
2. Reads GCP instance metadata (vm-agent-token, claude-token, wolfram-key, tier)
3. Writes `/home/explorer/.env` with VM agent config
4. Configures Claude CLI via `claude setup-token` (timeout 15s)
5. Activates Wolfram Engine via `wolframscript -activate` (timeout 30s)
6. Creates working directories

### vm-agent.service (long-running, starts after setup)

Runs uvicorn serving the VM agent on port 8080:
```
/opt/agent-conditioning/.venv/bin/uvicorn vm_agent.agent:app --host 0.0.0.0 --port 8080
```
- Reads token from `/home/explorer/.env`
- Restarts automatically on failure (RestartSec=5)

## Boot Sequence

```
GCP creates VM from base image
  ↓ Instance metadata injected: vm-agent-token, claude-token, wolfram-key, tier
  ↓
systemd starts explorer-setup.service
  ↓ vm-startup.sh executes:
  ↓   1. git pull (deploy keys, --ff-only, || true on failure)
  ↓   2. curl GCP metadata endpoint
  ↓   3. Write .env file
  ↓   4. claude setup-token (timeout 15s)
  ↓   5. wolframscript -activate (timeout 30s)
  ↓   6. mkdir data/ working/
  ↓
systemd starts vm-agent.service
  ↓ uvicorn on port 8080
  ↓
VM ready (~30-45s from boot)
```

## GCP Firewall Rules

| Rule | Direction | Allow | Source | Target |
|------|-----------|-------|--------|--------|
| allow-iap-ssh | INGRESS | tcp:22 | 35.235.240.0/20 (IAP) | explorer-vm tag |
| allow-vm-agent | INGRESS | tcp:8080 | 10.128.0.0/20 (internal) | explorer-vm tag |

User VMs have no external IP. SSH access via IAP tunneling only.
VM agent accessible only from the internal GCP network (backend).

## How to Rebuild the Base Image

### 1. Create a template VM

```bash
gcloud compute instances create agent-explorer-template \
    --project=agent-explorer-app \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-ssd \
    --tags=explorer-vm
```

Note: include an external IP for setup (package installation needs internet).

### 2. Copy files and SSH in

```bash
gcloud compute scp deploy_key_agent_conditioning deploy_key_auto_compact \
    vm-startup.sh agent-explorer-template:/tmp/ \
    --zone=us-central1-a --tunnel-through-iap

gcloud compute ssh agent-explorer-template \
    --zone=us-central1-a --tunnel-through-iap
```

### 3. Install everything

```bash
# System packages
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git curl

# Node.js + Claude CLI
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g @anthropic-ai/claude-code

# Explorer user
sudo useradd -m -s /bin/bash explorer
sudo mkdir -p /home/explorer/working /home/explorer/data
sudo chown -R explorer:explorer /home/explorer

# Deploy keys
sudo mkdir -p /opt/deploy-keys
sudo cp /tmp/deploy_key_* /opt/deploy-keys/
sudo chmod 600 /opt/deploy-keys/deploy_key_*
# Write SSH config (see deploy keys section above)

# Clone repos
sudo GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config -o HostKeyAlias=github-agent-conditioning" \
    git clone git@github-agent-conditioning:Jeremy-Adams-100/agent-conditioning.git /opt/agent-conditioning
sudo GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config -o HostKeyAlias=github-auto-compact" \
    git clone git@github-auto-compact:Jeremy-Adams-100/auto-compact.git /opt/auto-compact
sudo chown -R explorer:explorer /opt/agent-conditioning /opt/auto-compact

# Python venv
sudo -u explorer python3 -m venv /opt/agent-conditioning/.venv
sudo -u explorer /opt/agent-conditioning/.venv/bin/pip install \
    fastapi uvicorn[standard] httpx pyyaml prompt_toolkit anthropic
sudo -u explorer /opt/agent-conditioning/.venv/bin/pip install -e /opt/auto-compact
sudo -u explorer /opt/agent-conditioning/.venv/bin/pip install -e /opt/agent-conditioning

# Add platform dir to Python path
echo "/opt/agent-conditioning/platform" | sudo tee \
    /opt/agent-conditioning/.venv/lib/python3.12/site-packages/platform.pth

# Startup script + systemd services
sudo cp /tmp/vm-startup.sh /opt/vm-startup.sh
sudo chmod +x /opt/vm-startup.sh
# Install systemd units (see vm_setup/install.sh for full content)
sudo systemctl daemon-reload
sudo systemctl enable explorer-setup.service vm-agent.service

# (Optional) Install Wolfram Engine
# sudo dpkg -i WolframEngine_14.2.0_LINUX.deb
```

### 4. Clean up and snapshot

```bash
# Remove temp files and creds
sudo rm -f /home/explorer/.env
sudo rm -rf /home/explorer/data/* /home/explorer/working/*
sudo apt-get clean

# Remove external IP
gcloud compute instances delete-access-config agent-explorer-template \
    --zone=us-central1-a --access-config-name="external-nat"

# Stop VM
gcloud compute instances stop agent-explorer-template --zone=us-central1-a

# Create image
gcloud compute images create agent-explorer-base-v3 \
    --source-disk=agent-explorer-template \
    --source-disk-zone=us-central1-a \
    --family=agent-explorer \
    --description="Base image v3: ..."

# Clean up template VM
gcloud compute instances delete agent-explorer-template --zone=us-central1-a
```

## Adding Wolfram Engine

Wolfram Engine is free for personal/non-commercial use but requires
a manual download from wolfram.com (no public direct link).

### Steps

1. Go to https://www.wolfram.com/engine/ and sign in
2. Download the Linux .deb file (WolframEngine_XX.X.X_LINUX.deb)
3. Transfer to a running template VM:
   ```bash
   gcloud compute scp WolframEngine_*.deb agent-explorer-template:/tmp/ \
       --zone=us-central1-a --tunnel-through-iap
   ```
4. SSH in and install:
   ```bash
   sudo dpkg -i /tmp/WolframEngine_*.deb
   sudo rm /tmp/WolframEngine_*.deb
   ```
5. Verify:
   ```bash
   wolfram -run 'Print[1+1]'
   # Should output: 2
   ```
6. Re-snapshot the image (follow steps in section above)

The startup script already handles per-user activation via
`wolframscript -activate <key>` using the Wolfram key from
GCP metadata. No changes needed to the startup script.

## File Permissions Summary

| Path | Owner | Permissions | Notes |
|------|-------|-------------|-------|
| `/opt/agent-conditioning/` | explorer | Read/write | Code + venv |
| `/opt/auto-compact/` | explorer | Read/write | Library |
| `/opt/deploy-keys/` | root | 600 (keys) | Private keys |
| `/opt/vm-startup.sh` | root | 755 | Startup script |
| `/home/explorer/.env` | explorer | 600 | Written at boot |
| `/home/explorer/data/` | explorer | Read/write | sessions.db, state |
| `/home/explorer/working/` | explorer | Read/write | File tool scope |
