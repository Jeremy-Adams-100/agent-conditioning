# Stage 4: Backend API

## Goal

A backend that handles user auth, VM lifecycle, and proxies
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

### Data (proxied from VM)

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

### Why FastAPI

- Async — can handle many concurrent VM proxy requests
- Auto-generated API docs (useful during development)
- Python — same as the rest of the codebase
- Minimal boilerplate

## Backend ↔ VM Communication

The backend never runs exploration logic directly. It sends
commands to the VM's HTTP agent and proxies responses to the
frontend.

```
Frontend                Backend                 VM Agent
   │                       │                       │
   │ POST /api/explore/    │                       │
   │ start {topic}         │                       │
   │──────────────────────>│                       │
   │                       │ POST /start            │
   │                       │ {topic}                │
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

The backend is a pass-through. It adds auth (is this user allowed
to talk to this VM?) and nothing else.

## Data Model

```sql
-- Backend database (NOT sessions.db — that's on the VM)

CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    tier            TEXT DEFAULT 'free',
    claude_token    TEXT,           -- encrypted at rest
    wolfram_key     TEXT,           -- encrypted at rest
    vm_id           TEXT,
    vm_status       TEXT DEFAULT 'none',
    vm_agent_token  TEXT            -- auth token for VM HTTP agent
);
```

## Security

- All API endpoints require auth (except signup/login)
- Claude tokens and Wolfram keys encrypted at rest (Fernet symmetric)
- VM agent tokens are random 32-byte hex, generated at provisioning
- Backend ↔ VM communication over private network (no public exposure)
- Users can only access their own VM (enforced by backend routing)
- No user can see another user's sessions, files, or state

## What's NOT in Stage 4

- Rate limiting (add in Stage 6)
- API versioning (single version for now)
- Webhook notifications (polling is sufficient)
- Admin panel (use direct DB queries for now)
