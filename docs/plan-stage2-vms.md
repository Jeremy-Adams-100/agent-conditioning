# Stage 2: VM Provisioning

## Goal

When a user completes onboarding, a VM is provisioned with all
software pre-installed. The VM is the user's isolated research
environment. It starts on "explore", stops on "stop", and can
be resumed.

## VM Lifecycle

```
User signs up
    → Backend creates VM from base image
    → Injects Claude token + Wolfram key
    → VM status: ready

User clicks "explore [topic]"
    → Backend starts VM (if stopped)
    → Runs: exploration start "[topic]"
    → VM status: running

User clicks "stop"
    → Backend sends stop signal to VM
    → exploration.py saves state, exits
    → VM stays alive (or suspends to save cost)

User clicks "clear"
    → Backend sends clear signal to VM
    → State archived, context reset
    → VM stays alive

User inactive 24h
    → Backend suspends VM (saves disk, releases compute)
    → VM status: suspended

User returns
    → Backend resumes VM
    → User clicks "explore" or "resume"
```

## Base Image

A pre-built VM image containing everything except user-specific
credentials:

```
Base image contents:
├── /opt/agent-conditioning/     # read-only installation
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── conductor.py
│   │   ├── exploration.py
│   │   ├── exploration-score.yaml
│   │   ├── config.yaml          # template (tier-specific)
│   │   └── templates/
│   └── ...
├── /opt/auto-compact/           # read-only installation
├── /usr/local/bin/wolfram       # Wolfram Engine (pre-installed)
├── /usr/local/bin/claude        # Claude Code CLI (pre-installed)
└── /home/explorer/              # user's working directory
    ├── working/                 # file tool scope
    └── data/                    # sessions.db, state files
```

The base image is built once, updated when the platform updates.
User VMs are cloned from it.

## Provisioning Steps

1. Clone base image → new VM
2. Write Claude token to VM: `claude setup-token <token>`
3. Activate Wolfram: `wolframscript -activate <key>`
4. Write tier-specific config.yaml (free vs max parameters)
5. Mark VM as ready in the users table

## Cloud Provider Options

| Provider | VM Type | Cost (idle) | Cost (running) | Notes |
|----------|---------|-------------|----------------|-------|
| AWS EC2 | t3.medium | ~$0.002/hr stopped | ~$0.04/hr | EBS snapshots for suspend |
| GCP Compute | e2-medium | ~$0.002/hr stopped | ~$0.03/hr | Preemptible for cost savings |
| Hetzner | CPX21 | ~$0.006/hr | ~$0.006/hr | Cheapest, no suspend (always on) |
| Fly.io | Machines | $0 stopped | ~$0.003/hr | Auto-suspend built in |

### Recommendation

Start with **Fly.io Machines**. They have built-in suspend/resume
(machine stops when the process exits, starts when a request arrives),
no cost when stopped, and a simple API. The base image is a Docker
container.

If Fly.io doesn't meet needs (GPU, specific region), fall back to
AWS EC2 with stop/start automation.

## VM Communication

The backend communicates with each VM via SSH or a lightweight agent:

```
Backend → VM:
  - Start exploration: ssh explorer@vm "cd /opt/agent-conditioning && python -m agent.exploration start 'topic'"
  - Stop: ssh explorer@vm "touch /home/explorer/data/exploration.stop"
  - Clear: ssh explorer@vm "touch /home/explorer/data/exploration.clear"
  - Read files: ssh explorer@vm "cat /home/explorer/data/sessions.db" (or rsync)
  - Read status: ssh explorer@vm "cat /home/explorer/data/exploration_status.md"

VM → Backend:
  - Nothing. Backend polls or reads on demand.
```

Alternatively, a tiny HTTP agent on the VM (a 30-line Flask/FastAPI
app) that exposes:
- `POST /start {"topic": "..."}` → runs exploration
- `POST /stop` → creates stop signal
- `POST /clear` → creates clear signal
- `GET /status` → returns exploration_status.md
- `GET /files` → lists working directory
- `GET /files/<path>` → serves a file
- `GET /sessions?query=...` → queries sessions.db

This is simpler than SSH for the backend to integrate with and
naturally maps to the frontend's needs.

### Recommendation

Build the **tiny HTTP agent** on the VM. It's ~50 lines of code,
maps directly to the CLI commands, and is easier to integrate with
the web frontend than SSH. Secure it with a per-VM auth token
(generated at provisioning, known only to the backend).

## What's NOT in Stage 2

- Auto-scaling (handle manually until demand justifies it)
- GPU support (Wolfram runs on CPU; GPU is a future optimization)
- VM migration between regions
- Automated base image updates (manual rebuild + re-deploy)
