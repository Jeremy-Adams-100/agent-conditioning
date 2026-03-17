# Tier Configuration

## Two Tiers

| Parameter | Free | Max (Claude Max) |
|-----------|------|------------------|
| Claude model | Sonnet | Opus |
| Context window | 200,000 tokens | 1,000,000 tokens |
| Cycle cooldown | 1000s (~17 min) | 30s |
| Approx. cycles/hour | 3-4 | 120 |
| Approx. cycles/day | ~86 | 2,880 |
| Compaction threshold | 90% | 90% |
| Wolfram Engine | Full access | Full access |
| Session search (MCP) | Full access | Full access |
| File tools | Full access | Full access |
| Bash | Wolfram only | Wolfram only |
| Sessions.db | Full access | Full access |

## Why 300s Cooldown for Free

Claude Free gives roughly 25-30 messages per 5 hours (varies).
Each exploration cycle = 3 agent calls (researcher + worker + auditor).
At 1000s cooldown: ~3-4 cycles/hour = ~10 messages/hour. Over 5
hours, that's ~50 messages — conservative enough to stay under
Claude's free tier limits regardless of exact quota.

If the user hits Claude's rate limit anyway, the failure handler
kicks in: 60s pause on first failures, 10min backoff on 3+.

The 1000s cooldown is a starting point — adjust based on observed
rate limit behavior. Can be reduced if free limits are more generous
than expected, or increased to 1800s if limits are hit prematurely.

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
