# Agent Explorer — Multi-User Platform Plan

## What We're Building

A web platform where users type "explore [topic]" and get a
continuously running three-agent research loop (researcher → worker →
auditor) powered by their own Claude account and Wolfram Engine. The
platform handles authentication, VM provisioning, and live result
streaming. The user sees an evolving file explorer of their research
output.

## Design Principles

- **Simple and robust** — every component should be the simplest
  version that works reliably
- **No API billing** — runs on users' own Claude Max or Free accounts
  via `claude -p`
- **Architecture stays the same** — the exploration conductor,
  auto-compact, and agent-conditioning run identically for free and
  paid users. Only parameters change (cycle delays, context limits).
- **Users never see source code** — they see their sessions, logs,
  and research output. The platform is a service, not an open-source
  tool.

## Tiers

| | Free | Paid (Claude Max) |
|---|---|---|
| Claude account | Free Claude account | Claude Max plan |
| Context window | 200k tokens | 1M tokens |
| Cycle cooldown | 120s | 30s |
| Agent model | Sonnet | Opus |
| Wolfram Engine | Free (personal use) | Free (personal use)* |
| Sessions.db | Full access | Full access |
| File explorer | Full access | Full access |

*Future: option to link a commercial Mathematica license.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Website (Frontend)              │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Sign Up  │  │ Explore  │  │ File Explorer │  │
│  │ / Login  │  │ Search   │  │ / Session Log │  │
│  └──────────┘  │ Bar      │  │               │  │
│                └──────────┘  └───────────────┘  │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│               Backend API Server                 │
│                                                  │
│  - User auth (accounts, tiers)                   │
│  - VM lifecycle (provision, start, stop, destroy)│
│  - File/session proxy (streams from user's VM)   │
│  - Tier config (parameters per plan)             │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐
     │ User A  │ │ User B  │ │ User C  │
     │ VM      │ │ VM      │ │ VM      │
     │         │ │         │ │         │
     │ claude  │ │ claude  │ │ claude  │
     │ wolfram │ │ wolfram │ │ wolfram │
     │ agent-  │ │ agent-  │ │ agent-  │
     │ cond.   │ │ cond.   │ │ cond.   │
     │         │ │         │ │         │
     │ sessions│ │ sessions│ │ sessions│
     │ .db     │ │ .db     │ │ .db     │
     └─────────┘ └─────────┘ └─────────┘
```

Each user gets an isolated VM with their own:
- Claude CLI authenticated to their account
- Wolfram Engine activated under their license
- agent-conditioning installation (read-only)
- Working directory with sessions.db and output files

## Implementation Stages

| Stage | What | Details |
|-------|------|---------|
| 1 | User onboarding flow | Account creation, Claude/Wolfram linking |
| 2 | VM provisioning | Automated VM setup with pre-installed software |
| 3 | Website frontend | Search bar, file explorer, session viewer |
| 4 | Backend API | Auth, VM lifecycle, file/session proxy |
| 5 | Tier configuration | Free vs paid parameter tuning |
| 6 | Polish & hardening | Error handling, monitoring, cleanup |

Detailed plans for each stage are in separate documents:
- [Stage 1: User Onboarding](plan-stage1-onboarding.md)
- [Stage 2: VM Provisioning](plan-stage2-vms.md)
- [Stage 3: Frontend](plan-stage3-frontend.md)
- [Stage 4: Backend API](plan-stage4-backend.md)
- [Stage 5: Tier Configuration](plan-stage5-tiers.md)
