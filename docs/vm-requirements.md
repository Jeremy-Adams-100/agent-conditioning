# VM Requirements — Complete Dependency List

All dependencies needed to run agent-conditioning, auto-compact,
and wolfram-bridge on a user VM.

## System Binaries

| Binary | Version | Purpose | Install Method |
|--------|---------|---------|---------------|
| Python | 3.12+ | All Python code | `apt install python3 python3-venv` |
| Node.js | 22.x+ | Claude Code CLI runtime | `nodesource setup_22.x` |
| Claude Code CLI | latest | Model calls via `claude -p` | `npm install -g @anthropic-ai/claude-code` |
| Wolfram Engine | 14.3+ | Wolfram Language execution | Manual `.sh` installer from wolfram.com |
| wolframscript | 1.13+ | Wolfram activation + scripting | Included with Wolfram Engine |
| git | any | Code updates via deploy keys | `apt install git` |

## Python Packages (pip install)

### Required — Core

| Package | Min Version | Used By | Purpose |
|---------|------------|---------|---------|
| pyyaml | 6.0 | agent-conditioning | Config file parsing |
| anthropic | 0.39.0 | auto-compact | Anthropic API client (for compaction summaries) |
| prompt-toolkit | any | agent-conditioning | Interactive CLI input (orchestrator) |

### Required — Platform (VM Agent)

| Package | Min Version | Used By | Purpose |
|---------|------------|---------|---------|
| fastapi | 0.115 | vm_agent | HTTP agent on each VM |
| uvicorn[standard] | 0.34 | vm_agent | ASGI server for FastAPI |
| httpx | 0.27 | vm_agent, platform | HTTP client |

### Required — Platform (Backend only, NOT on user VMs)

| Package | Min Version | Used By | Purpose |
|---------|------------|---------|---------|
| bcrypt | 4.0 | platform backend | Password hashing |
| cryptography | 44.0 | platform backend | Fernet encryption for stored tokens |
| itsdangerous | 2.2 | platform backend | Signed session cookies |
| google-cloud-compute | 1.19 | platform backend | GCP VM lifecycle |

### Optional

| Package | Used By | Purpose | When Needed |
|---------|---------|---------|-------------|
| wolframclient | wolfram-bridge | Persistent Wolfram kernel sessions | Optional performance optimization |
| python-dotenv | wolfram-bridge | .env file loading | Only for local dev |
| setuptools | wolfram-bridge | Build backend | For editable install |

## Local Packages (editable install)

All three repos installed as editable packages in the venv:

```bash
pip install -e /opt/auto-compact
pip install -e /opt/agent-conditioning
pip install -e /opt/wolfram-bridge
```

Plus the platform path added for vm_agent imports:
```bash
echo "/opt/agent-conditioning/platform" > .venv/lib/python3.12/site-packages/platform.pth
```

## VM Venv Install Command (complete)

```bash
python3 -m venv /opt/agent-conditioning/.venv
/opt/agent-conditioning/.venv/bin/pip install \
    pyyaml \
    anthropic \
    prompt-toolkit \
    fastapi \
    'uvicorn[standard]' \
    httpx \
    setuptools

/opt/agent-conditioning/.venv/bin/pip install \
    -e /opt/auto-compact \
    -e /opt/agent-conditioning \
    -e /opt/wolfram-bridge

echo "/opt/agent-conditioning/platform" > \
    /opt/agent-conditioning/.venv/lib/python3.12/site-packages/platform.pth
```

## What Does NOT Go on User VMs

These are backend-only dependencies (run on the central server):

- bcrypt (password hashing)
- cryptography (Fernet for token storage)
- itsdangerous (signed cookies)
- google-cloud-compute (VM lifecycle)
- pydantic (FastAPI dependency, auto-installed)

## Verification Commands

After installing, run these to verify everything is importable:

```bash
VENV=/opt/agent-conditioning/.venv/bin/python

# Core
$VENV -c "from agent.exploration import load_exploration_score; print('agent-conditioning: OK')"
$VENV -c "from auto_compact.db import init_db; print('auto-compact: OK')"
$VENV -c "from wolfram_bridge.utils import find_wolfram_executable; print('wolfram-bridge: OK')"

# VM agent
PYTHONPATH=/opt/agent-conditioning/platform $VENV -c "from vm_agent.agent import app; print('vm-agent: OK')"

# System binaries
claude --version
wolfram -version
```
