# Stage 4: Backend API

## Goal

A backend that handles user auth, GCP VM lifecycle, and proxies
file/session data from user VMs to the frontend. Thin as
possible — the real work happens on the VMs.

## API Endpoints

### Auth

```
POST /api/auth/signup     {email, password}         → {user_id, token}
POST /api/auth/login      {email, password}         → {token}
POST /api/auth/logout                               → 204
```

### Onboarding

```
POST /api/onboard/claude   {claude_token}           → {plan: "free"|"max"}
POST /api/onboard/wolfram  {wolfram_key}            → {status: "ok"|"error"}
GET  /api/onboard/status                            → {claude: bool, wolfram: bool, vm: "none"|"ready"|...}
```

### Exploration Control

```
POST /api/explore/start    {topic}                  → {status: "starting"}
POST /api/explore/stop                              → {status: "stopping"}
POST /api/explore/clear                             → {status: "clearing"}
POST /api/explore/resume   {state_file?}            → {status: "resuming"}
```

### Data (proxied from VM agent)

```
GET  /api/status                                    → {cycle, agent, status, failures}
GET  /api/sessions                                  → [{id, cycle, agent, preview}...]
GET  /api/sessions/:id                              → {full session content}
GET  /api/files                                     → [{path, size, modified}...]
GET  /api/files/:path                               → file content
GET  /api/archives                                  → [{filename, timestamp}...]
```

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python (FastAPI) | Same as agent-conditioning. One language across the stack. |
| Database | SQLite | Users table. No need for PostgreSQL at this scale. |
| Auth | bcrypt + signed cookies | Simple. No JWTs, no OAuth server. |
| VM communication | HTTP to VM agent | Each VM runs a tiny HTTP agent (see Stage 2). |
| GCP client | `google-cloud-compute` Python library | Official, well-maintained. |
| Hosting | GCP Cloud Run or a single GCP VM | Backend is stateless, scales naturally on Cloud Run. |

## Backend ↔ VM Communication

The backend never runs exploration logic directly. It sends
commands to the VM's HTTP agent and proxies responses to the
frontend.

```
Frontend                Backend                 VM Agent (on GCP VM)
   │                       │                       │
   │ POST /api/explore/    │                       │
   │ start {topic}         │                       │
   │──────────────────────>│                       │
   │                       │ 1. Resume VM (if suspended)
   │                       │    gcp.resume_instance()
   │                       │                       │
   │                       │ 2. POST /start        │
   │                       │    {topic}             │
   │                       │──────────────────────>│
   │                       │                       │ runs exploration.py
   │                       │         200 OK        │
   │                       │<──────────────────────│
   │         200 OK        │                       │
   │<──────────────────────│                       │
   │                       │                       │
   │ GET /api/status       │                       │
   │──────────────────────>│                       │
   │                       │ GET /status            │
   │                       │──────────────────────>│
   │                       │ {cycle: 3, agent:...} │
   │                       │<──────────────────────│
   │  {cycle: 3, ...}     │                       │
   │<──────────────────────│                       │
```

The backend is a pass-through with two responsibilities:
1. Auth — is this user allowed to talk to this VM?
2. GCP lifecycle — resume suspended VMs before forwarding requests.

## VM Lifecycle Management

```python
# Thin wrapper around GCP Compute Engine API

async def ensure_vm_running(user):
    """Resume VM if suspended, start if stopped. No-op if running."""
    if user.vm_status == "suspended":
        await gcp.resume_instance(ZONE, user.vm_id)
        # Poll until VM agent responds (5-10s)
        await wait_for_vm_agent(user)
        user.vm_status = "running"
    elif user.vm_status == "stopped":
        await gcp.start_instance(ZONE, user.vm_id)
        await wait_for_vm_agent(user)
        user.vm_status = "running"

async def suspend_idle_vms():
    """Cron job: suspend VMs idle > 1 hour."""
    for user in get_users_with_running_vms():
        status = await call_vm_agent(user, "GET", "/status")
        if not is_exploration_running(status) and idle_over_1h(status):
            await gcp.suspend_instance(ZONE, user.vm_id)
            user.vm_status = "suspended"
```

## Data Model

```sql
-- Backend database (NOT sessions.db — that's on each user's VM)

CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    tier            TEXT DEFAULT 'free',    -- 'free' or 'max'
    claude_token    TEXT,                   -- encrypted (Fernet)
    wolfram_key     TEXT,                   -- encrypted (Fernet)
    vm_id           TEXT,                   -- GCP instance name
    vm_zone         TEXT DEFAULT 'us-central1-a',
    vm_status       TEXT DEFAULT 'none',    -- none/provisioning/ready/running/suspended
    vm_internal_ip  TEXT,                   -- GCP internal IP for VM agent
    vm_agent_token  TEXT                    -- auth token for VM HTTP agent
);
```

## Security

- All API endpoints require auth (except signup/login)
- Claude tokens and Wolfram keys encrypted at rest (Fernet symmetric)
- VM agent tokens are random 32-byte hex, generated at provisioning
- Backend ↔ VM communication over GCP internal network (no public IP on VMs)
- Users can only access their own VM (enforced by backend routing)
- No user can see another user's sessions, files, or state
- Backend hosted on same GCP project as VMs (private network)

## What's NOT in Stage 4

- Rate limiting (add in Stage 6)
- API versioning (single version for now)
- Webhook notifications (polling is sufficient)
- Admin panel (use direct DB queries for now)
- Multi-region routing (single region for now)
