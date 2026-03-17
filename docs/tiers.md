# Tier Configuration

## Two Tiers

| Parameter | Free | Max (Claude Max) |
|-----------|------|------------------|
| Claude model | Sonnet | Opus |
| Context window | 200,000 tokens | 1,000,000 tokens |
| Cycle cooldown | 300s (5 min) | 30s |
| Approx. cycles/hour | 12 | 120 |
| Approx. cycles/day | 288 | 2,880 |
| Compaction threshold | 90% | 90% |
| Wolfram Engine | Full access | Full access |
| Session search (MCP) | Full access | Full access |
| File tools | Full access | Full access |
| Bash | Wolfram only | Wolfram only |
| Sessions.db | Full access | Full access |

## Why 300s Cooldown for Free

Claude Free gives roughly 25-30 messages per 5 hours (varies).
Each exploration cycle = 3 agent calls (researcher + worker + auditor).
At 300s cooldown: ~12 cycles/hour = ~36 messages/hour. Over 5 hours,
that's ~180 messages — within Claude's free tier limits with headroom.

If the user hits Claude's rate limit anyway (e.g., agents use tools
that make additional calls), the failure handler kicks in:
- 1-2 failures: 60s pause
- 3+ failures: 10min backoff

The 300s cooldown prevents this from happening in normal operation.
Users get steady, continuous research without hitting walls.

At 120s cooldown (previously planned), users would exhaust Claude's
free quota in ~20 minutes and then face repeated 10-minute backoffs.
300s provides even pacing over the full day.

## What Does NOT Change Between Tiers

- The exploration conductor code
- Agent roles and conditioning (same philosophies, same frameworks)
- Compaction and session persistence logic
- File/session access model
- Bash restrictions (Wolfram only)
- Wolfram Engine access
- Security model

## Tier Detection

Automatic at VM provisioning:
1. VM agent runs `claude -p --model opus "Say ok"`
2. If opus responds → tier = "max"
3. If opus fails → tier = "free"

Users can re-check after upgrading via `POST /api/tier/check`.

## Upgrade Flow

1. User clicks "Upgrade" link in Q.E.D. header
2. Redirected to claude.ai/pricing (external — no payment on our side)
3. User upgrades their Claude account to Max
4. User returns to Q.E.D., clicks "Check my plan"
5. Backend calls VM agent → detects opus access → updates tier
6. VM startup script writes tier-specific config on next boot

No mid-exploration tier switching. User stops exploration, checks
tier, and starts again with the new configuration.

## Data Protection

Each user's VM is isolated:
- Own working directory, sessions.db, and state files
- GCP encrypts all data at rest (AES-256, Google-managed keys)
- No cross-user VM access
- Deploy keys are read-only
- VM agent only exposes files within the working directory

For users with sensitive IP requiring additional protection:
CMEK (Customer-Managed Encryption Keys) via GCP KMS is a future
option where the user controls the encryption key and can revoke
access at any time. See future-work.md.
