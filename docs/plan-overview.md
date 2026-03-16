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
  via `claude -p`. Each user authenticates their own Claude account.
- **Architecture stays the same** — the exploration conductor,
  auto-compact, and agent-conditioning run identically for free and
  paid users. Only parameters change (cycle delays, context limits).
- **Users never see source code** — they see their sessions, logs,
  and research output. The platform is a service, not an open-source
  tool.

## Tiers

| | Free | Paid (Claude Max) |
|---|---|---|
| Claude account | Free Claude account (user-provided) | Claude Max plan (user-provided) |
| Context window | 200k tokens | 1M tokens |
| Cycle cooldown | 120s | 30s |
| Agent model | Sonnet | Opus |
| Wolfram Engine | Free (personal use, user-activated) | Free (personal use)* |
| Sessions.db | Full access | Full access |
| File explorer | Full access | Full access |

*Future: option to link a commercial Mathematica license.

No payment processing on the platform. Users upgrade directly with
Anthropic (Claude Max) and the platform detects the upgrade.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Website (Next.js on Vercel)            │
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
│          Backend API (FastAPI on GCP)             │
│                                                  │
│  - User auth (accounts, tiers)                   │
│  - GCP VM lifecycle (create, suspend, resume)    │
│  - File/session proxy (from user's VM)           │
│  - Tier config (parameters per plan)             │
└────────────────────┬────────────────────────────┘
                     │ GCP internal network
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐
     │ User A  │ │ User B  │ │ User C  │
     │ GCP VM  │ │ GCP VM  │ │ GCP VM  │
     │         │ │         │ │         │
     │ claude  │ │ claude  │ │ claude  │
     │ wolfram │ │ wolfram │ │ wolfram │
     │ agent-  │ │ agent-  │ │ agent-  │
     │ cond.   │ │ cond.   │ │ cond.   │
     │         │ │         │ │         │
     │ sessions│ │ sessions│ │ sessions│
     │ .db     │ │ .db     │ │ .db     │
     │         │ │         │ │         │
     │ VM agent│ │ VM agent│ │ VM agent│
     │ (HTTP)  │ │ (HTTP)  │ │ (HTTP)  │
     └─────────┘ └─────────┘ └─────────┘
```

Each user gets an isolated GCP Compute Engine VM with:
- Claude CLI authenticated to their own account (via token paste)
- Wolfram Engine activated under their own license key
- agent-conditioning installation (read-only)
- Working directory with sessions.db and output files
- Tiny HTTP agent for backend communication

VMs suspend when idle (GCP native suspend — memory preserved,
~$0.04/GB/month disk cost only). Resume is instant.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| VM provider | GCP Compute Engine | 99.99% SLA, native suspend/resume, cheapest idle cost, Python client libraries |
| Claude auth | Token paste (`claude setup-token`) | Simplest onboarding, <5 min setup |
| Wolfram auth | License key paste + automated activation | Same simplicity, automated verification |
| Frontend | Next.js | SSR landing + client explorer in one project |
| Backend | FastAPI (Python) | Same language as agent-conditioning, async |
| VM communication | HTTP agent on each VM | Simple REST API, no SSH complexity |
| Polling (not WebSockets) | Frontend polls every 5s | Simpler, works everywhere, cycles take minutes |

## Implementation Stages

| Stage | What | Details |
|-------|------|---------|
| 1 | User onboarding flow | Account creation, Claude/Wolfram linking |
| 2 | VM provisioning | GCP VM setup with base image + credential injection |
| 3 | Website frontend | Search bar, file explorer, session viewer |
| 4 | Backend API | Auth, GCP VM lifecycle, file/session proxy |
| 5 | Tier configuration | Free vs Max parameter tuning |
| 6 | Polish & hardening | Error handling, monitoring, cleanup |

Detailed plans for each stage:
- [Stage 1: User Onboarding](plan-stage1-onboarding.md)
- [Stage 2: VM Provisioning](plan-stage2-vms.md)
- [Stage 3: Frontend](plan-stage3-frontend.md)
- [Stage 4: Backend API](plan-stage4-backend.md)
- [Stage 5: Tier Configuration](plan-stage5-tiers.md)
- [VM Provider Comparison](plan-vm-comparison.md)
