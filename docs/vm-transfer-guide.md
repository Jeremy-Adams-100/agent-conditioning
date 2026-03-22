# Q.E.D. — VM Transfer Guide

Complete instructions for setting up Q.E.D. on a new virtual desktop.
Covers all repos, dependencies, secrets, and configuration.

Date: 2026-03-22
Source VM: ip-10-7-81-93 (AWS, Ubuntu 24.04, x86_64)

---

## Step 1: Clone Repositories

```bash
cd ~

# Agent Conditioning (main platform — use feature/reporter-agent branch)
git clone https://github.com/Jeremy-Adams-100/agent-conditioning.git
cd agent-conditioning && git checkout feature/reporter-agent && cd ~

# Wolfram Bridge (Wolfram Language bridge + exploration workspace)
git clone https://github.com/Jeremy-Adams-100/wolfram-bridge.git

# Auto Compact (context management library)
git clone https://github.com/Jeremy-Adams-100/auto-compact.git
```

---

## Step 2: Environment Secrets

### ~/.env
```bash
cat > ~/.env << 'EOF'
GITHUB_TOKEN=<your-github-personal-access-token>
EOF
chmod 600 ~/.env
```

### agent-conditioning/platform/.env
```bash
cat > ~/agent-conditioning/platform/.env << 'EOF'
PLATFORM_FERNET_KEY=<your-fernet-key>
PLATFORM_COOKIE_SECRET=<your-cookie-secret>
GCP_PROJECT=agent-explorer-app
GCP_ZONE=us-central1-a
GCP_BASE_IMAGE=agent-explorer-base-v4
GCP_MACHINE_TYPE=e2-medium
GCP_MOCK=true
EOF
chmod 600 ~/agent-conditioning/platform/.env
```

**Get your actual secrets from the old VM:**
- `~/.env` — copy the GITHUB_TOKEN value
- `~/agent-conditioning/platform/.env` — copy FERNET_KEY and COOKIE_SECRET

---

## Step 3: Deploy Keys

Create the directory and copy keys (or regenerate if needed):

```bash
mkdir -p ~/deploy-keys
chmod 700 ~/deploy-keys

# Copy these files from the old VM:
#   deploy_key_agent_conditioning      (private)
#   deploy_key_agent_conditioning.pub  (public)
#   deploy_key_auto_compact            (private)
#   deploy_key_auto_compact.pub        (public)
#   deploy_key_wolfram_bridge          (private)
#   deploy_key_wolfram_bridge.pub      (public)
#
# Then set permissions:
chmod 600 ~/deploy-keys/deploy_key_*
chmod 644 ~/deploy-keys/*.pub
```

These are read-only deploy keys for each GitHub repo, used by the
VM startup script to pull latest code onto user VMs.

---

## Step 4: Install Wolfram Engine

Download from https://www.wolfram.com/engine/ (free for personal use).

```bash
# Install the .deb package
sudo dpkg -i WolframEngine_*.deb

# Create symlink in ~/bin
mkdir -p ~/bin
ln -s /path/to/Mathematica/Executables/wolfram ~/bin/wolfram

# Activate (one-time)
wolframscript -activate YOUR_WOLFRAM_KEY

# Verify
~/bin/wolfram -run 'Print[1+1]'
# Should print: 2
```

Note: The exact Mathematica path depends on the install location.
On the old VM it was: `/data/home/jadams2/Mathematica/Executables/wolfram`

---

## Step 5: Install Pandoc + Tectonic

These are used for PDF report generation.

```bash
mkdir -p ~/bin

# Pandoc (extract from .deb without sudo)
curl -sL https://github.com/jgm/pandoc/releases/download/3.6.4/pandoc-3.6.4-1-amd64.deb -o /tmp/pandoc.deb
cd /tmp && ar x pandoc.deb && tar xf data.tar.gz
cp /tmp/usr/bin/pandoc ~/bin/pandoc
chmod +x ~/bin/pandoc
rm -rf /tmp/pandoc.deb /tmp/data.tar.* /tmp/control.tar.* /tmp/debian-binary /tmp/usr

# Tectonic
curl -sL https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-gnu.tar.gz \
    | tar xz -C ~/bin
chmod +x ~/bin/tectonic

# Verify
pandoc --version | head -1
tectonic --version
```

Ensure `~/bin` is on your PATH:
```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## Step 6: Install Claude CLI

```bash
# Requires Node.js 22+
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
npm install -g @anthropic-ai/claude-code

# Verify
claude --version
```

---

## Step 7: Install Google Cloud SDK

Only needed if deploying user VMs to GCP.

```bash
curl https://sdk.cloud.google.com | bash
# Follow prompts, then restart shell
gcloud init
gcloud auth login
```

---

## Step 8: Install Python Dependencies

```bash
# Platform backend
cd ~/agent-conditioning/platform
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn[standard] httpx pyyaml bcrypt \
    cryptography anthropic itsdangerous python-dotenv

# Install auto-compact as editable
.venv/bin/pip install -e ~/auto-compact

# Install agent-conditioning itself (for orchestrator imports)
cd ~/agent-conditioning
.venv/bin/pip install -e ~/auto-compact  # if needed from agent dir too
```

---

## Step 9: Install Frontend Dependencies

```bash
cd ~/agent-conditioning/frontend
npm install
```

---

## Step 10: Claude Code Settings

### ~/.claude/settings.json
```json
{
  "effortLevel": "high"
}
```

### ~/.claude/settings.local.json

This file contains tool permission grants accumulated over time.
The essential QED-related permissions are:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(python:*)",
      "Bash(pip install:*)",
      "Bash(echo:*)",
      "Bash(git init:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push:*)",
      "Bash(git pull:*)",
      "Bash(git fetch:*)",
      "Bash(git checkout:*)",
      "Bash(git merge:*)",
      "Bash(git branch:*)",
      "Bash(git remote:*)",
      "Bash(git stash:*)",
      "Bash(git status:*)",
      "Bash(git rm:*)",
      "Bash(git reset:*)",
      "Bash(git -C:*)",
      "Bash(find:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(grep:*)",
      "Bash(head:*)",
      "Bash(tree:*)",
      "Bash(du -sh:*)",
      "Bash(wc -l:*)",
      "Bash(chmod:*)",
      "Bash(ps:*)",
      "Bash(bash:*)",
      "Bash(source:*)",
      "Bash(curl:*)",
      "Bash(node:*)",
      "Bash(npm:*)",
      "Bash(npm run:*)",
      "Bash(uv:*)",
      "Bash(uv run:*)",
      "Bash(uv sync:*)",
      "Bash(uv pip:*)",
      "Bash(uv lock:*)",
      "Bash(uv build:*)",
      "Bash(wolfram:*)",
      "Bash(wolframscript:*)",
      "Bash(~/bin/wolfram:*)",
      "Bash(timeout:*)",
      "Bash(pandoc:*)",
      "Bash(tectonic:*)",
      "Bash(pdfinfo:*)",
      "Bash(pdftotext:*)",
      "Bash(sqlite3:*)",
      "Bash(python3 -c:*)",
      "Bash(gh:*)",
      "Bash(gcloud:*)",
      "Bash(rm:*)",
      "Bash(xargs:*)",
      "Bash(sort:*)",
      "Bash(which:*)",
      "WebSearch",
      "WebFetch(domain:reference.wolfram.com)",
      "WebFetch(domain:wolframresearch.github.io)",
      "Read(//tmp/**)"
    ]
  }
}
```

Note: this is a cleaned-up version of the original. The old VM had
181 accumulated rules including many one-off commands. The above covers
all the essential tools for QED development.

---

## Step 11: Create Workspace Directories

```bash
mkdir -p ~/agent-conditioning/agent/data
mkdir -p ~/agent-conditioning/agent/output
mkdir -p ~/interact
```

---

## Step 12: Optional — Restore State

If you want continuity from the old VM:

```bash
# Exploration session history (copy from old VM)
cp old_vm/agent-conditioning/agent/data/sessions.db \
   ~/agent-conditioning/agent/data/sessions.db

# User accounts for mock mode (copy from old VM)
cp old_vm/agent-conditioning/platform/data/users.db \
   ~/agent-conditioning/platform/data/users.db
```

If starting fresh, these are created automatically on first use.

---

## Step 13: Start the Development Server

```bash
cd ~/agent-conditioning
./dev-start.sh
```

This starts three services:
- VM agent on :8080
- Platform API on :8000
- Frontend on :3000

Open http://localhost:3000 in your browser.

---

## Directory Layout (for reference)

```
~/
├── agent-conditioning/     ← Main platform (git repo)
│   ├── agent/              ← Orchestrator, exploration, config
│   ├── frontend/           ← Next.js frontend
│   ├── platform/           ← FastAPI backend + VM agent
│   ├── docs/               ← Documentation
│   └── dev-start.sh        ← Start all services
├── wolfram-bridge/         ← Wolfram bridge + workspace (git repo)
│   ├── wolfram_bridge/     ← Python bridge package
│   ├── pde_solver/         ← PDE solver library
│   └── quantum_foundations/← Exploration output
├── auto-compact/           ← Context management (git repo)
├── deploy-keys/            ← SSH deploy keys for VM provisioning
├── interact/               ← Interact agent workspace (auto-created)
├── bin/                    ← pandoc, tectonic, wolfram symlink
├── Mathematica/            ← Wolfram Engine installation
├── google-cloud-sdk/       ← GCP SDK (if needed)
└── .env                    ← GitHub token
```

---

## Troubleshooting

**"Module not found" on dev-start.sh:**
Check that auto-compact is installed as editable in the platform venv:
`cd ~/agent-conditioning/platform && .venv/bin/pip install -e ~/auto-compact`

**"wolfram: command not found":**
Verify the symlink: `ls -la ~/bin/wolfram`
Verify PATH includes ~/bin: `echo $PATH`

**"pandoc: command not found":**
Same — verify ~/bin/pandoc exists and ~/bin is on PATH.

**Frontend build errors:**
`cd ~/agent-conditioning/frontend && rm -rf node_modules && npm install`

**"exploration.stop" stale signal on start:**
`rm -f ~/agent-conditioning/agent/data/exploration.stop`
