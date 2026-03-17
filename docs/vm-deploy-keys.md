# VM Deploy Keys

Three read-only deploy keys are required for VMs to pull code on boot.

## Keys Required

| Key | GitHub Repo | SSH Config Host |
|-----|-------------|-----------------|
| `deploy_key_agent_conditioning` | Jeremy-Adams-100/agent-conditioning | github-agent-conditioning |
| `deploy_key_auto_compact` | Jeremy-Adams-100/auto-compact | github-auto-compact |
| `deploy_key_wolfram_bridge` | Jeremy-Adams-100/wolfram-bridge | github-wolfram-bridge |

## Setup

### Generate keys (if needed)

```bash
ssh-keygen -t ed25519 -f deploy_key_agent_conditioning -N "" -C "agent-conditioning-vm"
ssh-keygen -t ed25519 -f deploy_key_auto_compact -N "" -C "auto-compact-vm"
ssh-keygen -t ed25519 -f deploy_key_wolfram_bridge -N "" -C "wolfram-bridge-vm"
```

### Add public keys to GitHub

For each repo, go to Settings → Deploy keys → Add deploy key:
- Paste the `.pub` file content
- Check "Allow read access" only
- Name: e.g., "VM (read-only)"

### Install on VM base image

```bash
sudo mkdir -p /opt/deploy-keys
sudo cp deploy_key_* /opt/deploy-keys/
sudo chmod 600 /opt/deploy-keys/deploy_key_*

sudo tee /opt/deploy-keys/ssh_config > /dev/null << 'EOF'
Host github-agent-conditioning
    Hostname github.com
    IdentityFile /opt/deploy-keys/deploy_key_agent_conditioning
    StrictHostKeyChecking accept-new

Host github-auto-compact
    Hostname github.com
    IdentityFile /opt/deploy-keys/deploy_key_auto_compact
    StrictHostKeyChecking accept-new

Host github-wolfram-bridge
    Hostname github.com
    IdentityFile /opt/deploy-keys/deploy_key_wolfram_bridge
    StrictHostKeyChecking accept-new
EOF
```

### Clone repos on VM

```bash
GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config -o HostKeyAlias=github-agent-conditioning" \
    git clone git@github-agent-conditioning:Jeremy-Adams-100/agent-conditioning.git /opt/agent-conditioning

GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config -o HostKeyAlias=github-auto-compact" \
    git clone git@github-auto-compact:Jeremy-Adams-100/auto-compact.git /opt/auto-compact

GIT_SSH_COMMAND="ssh -F /opt/deploy-keys/ssh_config -o HostKeyAlias=github-wolfram-bridge" \
    git clone git@github-wolfram-bridge:Jeremy-Adams-100/wolfram-bridge.git /opt/wolfram-bridge
```

The startup script (`vm-startup.sh`) pulls all three repos on every boot.
