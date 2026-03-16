# Stage 3: Frontend

## Goal

A minimal, professional website with three views: onboarding,
explorer (search bar + live results), and file browser. No
unnecessary UI. Clean, fast, functional.

## Views

### 1. Landing / Login

```
┌─────────────────────────────────────────────┐
│                                             │
│            Agent Explorer                   │
│                                             │
│     Continuous autonomous research          │
│     powered by Claude and Wolfram           │
│                                             │
│     [Sign Up]    [Log In]                   │
│                                             │
└─────────────────────────────────────────────┘
```

No feature lists, no marketing copy, no screenshots. Just the
name, one line, and two buttons.

### 2. Explorer (main view after login)

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Explorer              [Free Plan | Upgrade]  [Logout]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  explore [___________________________________] [Go]         │
│                                                             │
│  Status: Running · Cycle 12 · Researcher active             │
│  [Stop]  [Clear]  [Resume]                                  │
│                                                             │
├───────────────────────┬─────────────────────────────────────┤
│  Sessions             │  Cycle 12 — Researcher              │
│                       │                                     │
│  ▸ Cycle 12          │  ## Current Sub-Topic                │
│    researcher ●       │  Wavefront sets and microlocal      │
│    worker             │  regularity...                      │
│    auditor            │                                     │
│  ▸ Cycle 11          │  ## Key Questions                    │
│    researcher         │  1. How do wavefront sets encode    │
│    worker             │     singularity information?        │
│    auditor ✓          │  2. ...                             │
│  ▸ Cycle 10          │                                     │
│    ...                │                                     │
│                       │                                     │
│  Files                │                                     │
│  ▸ working/           │                                     │
│    analysis.wls       │                                     │
│    wavefront.wl       │                                     │
│                       │                                     │
└───────────────────────┴─────────────────────────────────────┘
```

**Left panel:** Session list (from sessions.db, grouped by cycle)
and file tree (from working directory). Click to view.

**Right panel:** Content viewer. Shows the selected session output
or file contents. Updates live when the active agent produces output.

**Top bar:** Search/explore input, status line, control buttons.

### 3. Onboarding (see Stage 1)

Three-step wizard: account → Claude → Wolfram.

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Framework | Next.js (App Router) | SSR for landing, client for explorer. Single project. |
| Styling | Tailwind CSS | Utility classes, no custom CSS files. Professional defaults. |
| State | React state + SWR | SWR for polling VM status/files. No Redux. |
| Auth | Cookie-based sessions | Simple. JWT is over-engineering for this. |
| Hosting | Vercel or Fly.io | Next.js native hosting. Free tier available. |

### Why Next.js

- SSR landing page (SEO, fast load)
- Client-side explorer view (interactive, polling)
- API routes for backend (same project)
- One deploy, one repo
- Largest ecosystem for this type of app

### Alternative: Plain HTML + HTMX

If Next.js feels heavy, the entire frontend could be:
- Static HTML/CSS for landing and onboarding
- HTMX for the explorer (poll for updates, swap DOM fragments)
- A Python backend (FastAPI) serving everything

This is simpler but less polished. Start with Next.js; fall back
to HTMX if the JS ecosystem becomes a burden.

## Polling Strategy

The frontend polls the backend for updates:

```
Every 5s while exploration is running:
  GET /api/status         → cycle number, active agent, running/stopped
  GET /api/sessions/latest → latest session output (if changed)

On user action:
  GET /api/files          → file tree
  GET /api/files/<path>   → file content
  GET /api/sessions?cycle=N → all sessions for a cycle
```

No WebSockets. Polling is simpler, works everywhere, and 5s
granularity is fine for cycles that take minutes.

## What's NOT in Stage 3

- Real-time streaming of agent output (polling is sufficient)
- Markdown rendering with math (add in Stage 6 with KaTeX)
- Mobile-responsive layout (desktop-first, mobile later)
- Dark mode (add later if requested)
- User settings page (edit in onboarding flow for now)
