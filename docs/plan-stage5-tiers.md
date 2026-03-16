# Stage 5: Tier Configuration

## Goal

Free and paid tiers run the same code. The only difference is a
config file written to the VM at provisioning time. No feature
flags, no conditional logic in the exploration conductor.

## Tier Parameters

```yaml
# config-free.yaml — written to free-tier VMs
model: sonnet
context_window: 200000
compact_threshold: 0.90

# exploration-score overrides
loop:
  cycle_cooldown_seconds: 120
```

```yaml
# config-max.yaml — written to Max-tier VMs
model: opus
context_window: 1000000
compact_threshold: 0.90

# exploration-score overrides
loop:
  cycle_cooldown_seconds: 30
```

## What Changes Per Tier

| Parameter | Free | Max | Where |
|-----------|------|-----|-------|
| `model` | sonnet | opus | config.yaml |
| `context_window` | 200,000 | 1,000,000 | config.yaml |
| `cycle_cooldown_seconds` | 120 | 30 | exploration-score.yaml |
| `compact_threshold` | 0.90 | 0.90 | Same |
| `allowed_tools` | Same | Same | Same |
| `agent philosophies` | Same | Same | Same |

## What Does NOT Change

- The exploration conductor code
- The agent roles and conditioning
- The compaction and session persistence logic
- The file/session access model
- The Bash restrictions (Wolfram only)

## Tier Detection

At onboarding, when the user connects their Claude account:

1. Backend stores the Claude token
2. Backend provisions VM with the token
3. VM runs: `claude -p --output-format json --model opus "Say ok"`
4. If it succeeds → user has Max (or at least access to Opus)
5. If it fails (rate limit or model unavailable) → user has Free
6. Backend sets `tier` in users table
7. Backend writes the appropriate config file to the VM

Re-check periodically (e.g., on each "explore" start) in case
the user upgraded their Claude plan.

## Upgrade Flow

```
User clicks "Upgrade" on the website
    → Link to claude.ai/pricing (upgrade externally)
    → User returns, clicks "Check my plan"
    → Backend re-runs tier detection on VM
    → If Max detected: update config, restart exploration
    → User sees: "Plan: Max · Opus · 1M context"
```

No payment processing on our side. Users upgrade directly with
Anthropic. We detect the upgrade and adjust configuration.

## What's NOT in Stage 5

- Mid-exploration tier switching (stop + restart is fine)
- Custom tier parameters (only free and max for now)
- Usage tracking / quotas (Claude handles rate limiting)
- Billing dashboard (no billing — users pay Anthropic directly)
