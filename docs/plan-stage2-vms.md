# Stage 2: VM Provisioning (GCP Compute Engine) — COMPLETE

**Status:** Implemented and tested. 24 tests passing (Stage 1 + 2).
**Code:** `platform/explorer_platform/` (gcp.py, vm_client.py, provision.py, explore.py, proxy.py, idle.py)
**VM agent:** `platform/vm_agent/agent.py`
**Setup scripts:** `platform/vm_setup/` (install.sh, vm-startup.sh)
**Base image:** `agent-explorer-base-v3` (Ubuntu 24.04 + Claude CLI 2.1.77 + Wolfram Engine 14.3.0 + Python 3.12 + deploy keys)
**GCP project:** `agent-explorer-app`
**Detailed setup reference:** [VM Setup Guide](vm-setup-guide.md)

## Goal

When a user completes onboarding, a GCP VM is provisioned from a
base image with all software pre-installed. Credentials are injected
automatically. The VM suspends when idle and resumes instantly.

## VM Lifecycle

```
User signs up + connects Claude + Wolfram
    → Backend calls GCP API: create VM from base image
    → Startup script injects Claude token + Wolfram key
    → VM status: ready

User types "explore [topic]"
    → Backend resumes VM (if suspended)
    → Backend calls VM agent: POST /start {"topic": "..."}
    → VM agent runs exploration.py
    → VM status: running

User clicks "stop"
    → Backend calls VM agent: POST /stop
    → exploration.py saves state, exits
    → VM stays alive for quick resume

User clicks "clear"
    → Backend calls VM agent: POST /clear
    → State archived, context reset
    → VM stays alive

User inactive 1h
    → Backend calls GCP API: suspend VM
    → Memory + disk saved, compute released
    → Cost: ~$0.04/GB/month disk only
    → VM status: suspended

User returns
    → Backend calls GCP API: resume VM (~5-10s)
    → User clicks "explore" or "resume"
    → VM agent picks up where it left off
```

## GCP Instance Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| Machine type | e2-medium | 2 vCPU, 4GB RAM. Sufficient for claude -p + wolfram |
| Boot disk | 20GB SSD | Sessions.db + working files + base software |
| Image | Custom image (built from base) | Pre-installed: claude, wolfram, agent-conditioning |
| Region | us-central1 | Cheapest. Add regions as demand grows. |
| Network | VPC internal only + VM agent port | No public IP. Backend communicates via internal network. |
| Service account | Minimal (no GCP API access from VM) | VMs cannot call GCP APIs or access other VMs |

### Cost Per VM

| State | Cost | At 100 users | At 1000 users |
|-------|------|-------------|---------------|
| Running | ~$0.034/hr ($25/mo) | $2,500/mo | $25,000/mo |
| Suspended | ~$0.80/mo (20GB disk) | $80/mo | $800/mo |

With 10% active: 100 users = ~$330/mo. 1000 users = ~$3,300/mo.

## Base Image

Built once via Packer or a manual snapshot, updated on platform releases.

```
Base image contents:
├── /opt/agent-conditioning/     # read-only
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── conductor.py
│   │   ├── exploration.py
│   │   ├── exploration-score.yaml
│   │   ├── mcp_search_server.py
│   │   ├── config.yaml.free      # tier template
│   │   ├── config.yaml.max       # tier template
│   │   └── templates/
│   └── ...
├── /opt/auto-compact/           # read-only
├── /opt/vm-agent/               # tiny HTTP agent (~50 lines)
│   └── agent.py
├── /usr/local/bin/wolfram       # Wolfram Engine (pre-installed, not activated)
├── /usr/local/bin/claude        # Claude Code CLI (pre-installed, not authenticated)
└── /home/explorer/              # user's writable space
    ├── working/                 # file tool scope (working_directory)
    └── data/                    # sessions.db, exploration_state.json
```

## Provisioning Steps (automated by backend)

```python
# 1. Create VM from base image
instance = gcp.create_instance(
    name=f"explorer-{user_id[:8]}",
    machine_type="e2-medium",
    source_image="agent-explorer-base-v1",
    zone="us-central1-a",
    metadata={
        "claude-token": encrypt(user.claude_token),
        "wolfram-key": encrypt(user.wolfram_key),
        "tier": user.tier,
        "vm-agent-token": generate_token(),
    },
)

# 2. Startup script on the VM (runs automatically on first boot):
#    - Read metadata: claude-token, wolfram-key, tier
#    - claude setup-token <token>
#    - wolframscript -activate <key>
#    - cp config.yaml.<tier> config.yaml
#    - Start vm-agent on port 8080
#    - Mark ready

# 3. Backend polls until VM agent responds on /status
# 4. Update users table: vm_id, vm_status="ready"
```

## VM Agent (HTTP)

A tiny FastAPI app running on each VM. Secured with a per-VM token.

```python
# /opt/vm-agent/agent.py (~50 lines)

from fastapi import FastAPI, Header, HTTPException
import subprocess, os, json
from pathlib import Path

app = FastAPI()
TOKEN = os.environ["VM_AGENT_TOKEN"]
DATA_DIR = Path("/home/explorer/data")
WORKING_DIR = Path("/home/explorer/working")

def auth(authorization: str = Header()):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401)

@app.post("/start")
def start(body: dict, _=Depends(auth)):
    topic = body.get("topic", "")
    cmd = ["python", "-m", "agent.exploration", "start"] + ([topic] if topic else [])
    subprocess.Popen(cmd, cwd="/opt/agent-conditioning")
    return {"status": "starting"}

@app.post("/stop")
def stop(_=Depends(auth)):
    (DATA_DIR / "exploration.stop").write_text("")
    return {"status": "stopping"}

@app.post("/clear")
def clear(_=Depends(auth)):
    (DATA_DIR / "exploration.clear").write_text("")
    return {"status": "clearing"}

@app.get("/status")
def status(_=Depends(auth)):
    path = DATA_DIR / "exploration_status.md"
    state_path = DATA_DIR / "exploration_state.json"
    result = {"status": "idle"}
    if path.exists():
        result["status_md"] = path.read_text()
    if state_path.exists():
        result["state"] = json.loads(state_path.read_text())
    return result

@app.get("/files")
def list_files(_=Depends(auth)):
    files = []
    for p in WORKING_DIR.rglob("*"):
        if p.is_file():
            files.append({"path": str(p.relative_to(WORKING_DIR)),
                          "size": p.stat().st_size,
                          "modified": p.stat().st_mtime})
    return files

@app.get("/files/{path:path}")
def get_file(path: str, _=Depends(auth)):
    full = WORKING_DIR / path
    if not full.is_file() or not full.resolve().is_relative_to(WORKING_DIR):
        raise HTTPException(404)
    return {"content": full.read_text(errors="replace")}

@app.get("/sessions")
def list_sessions(query: str = None, limit: int = 20, _=Depends(auth)):
    from auto_compact.db import init_db, search_sessions, list_session_catalog
    conn = init_db(DATA_DIR / "sessions.db")
    if query:
        return search_sessions(conn, query, limit)
    return list_session_catalog(conn, limit=limit)

@app.get("/sessions/{session_id}")
def get_session(session_id: str, _=Depends(auth)):
    from auto_compact.db import init_db, get_session_by_id
    conn = init_db(DATA_DIR / "sessions.db")
    s = get_session_by_id(conn, session_id)
    if not s:
        raise HTTPException(404)
    return s
```

## Suspend / Resume (GCP Native)

GCP suspend preserves the VM's memory and disk state. Resume
restores the VM to exactly where it was — processes, file handles,
network connections all intact. The VM agent process resumes
automatically.

```python
# Backend: suspend idle VM
gcp.suspend_instance(zone, instance_name)
# Cost drops from ~$0.034/hr to ~$0.001/hr (disk only)

# Backend: resume on user request
gcp.resume_instance(zone, instance_name)
# VM available in ~5-10 seconds
```

### Idle Detection

Backend checks each running VM every 15 minutes:
- Call VM agent: GET /status
- If exploration is not running AND last activity > 1 hour → suspend

Simple cron job. No complex idle detection logic.

## What's NOT in Stage 2

- Auto-scaling (manual VM management until demand justifies it)
- Multi-region (start with us-central1, add regions later)
- GPU support (Wolfram + Claude run on CPU)
- Live VM migration
- Automated base image CI/CD (manual rebuild + re-snapshot)
