# Stage 7: Scaling

## Goal

Handle rapid adoption (1000+ users/day) without provisioning
bottlenecks, quota failures, or zone capacity issues.

## Current Bottlenecks

| Bottleneck | Current State | Impact |
|------------|--------------|--------|
| Sequential provisioning | BackgroundTask, one at a time | 1000 users = ~12 hours |
| GCP VM quota | Default ~24 per zone | Hard cap, blocks new users |
| Single zone | us-central1-a only | Zone capacity limits |
| Single backend process | One FastAPI instance | HTTP fine, provisioning bottleneck |

## Fixes Required

### 1. Parallel VM Provisioning

Replace BackgroundTasks with a task queue. Options:

| Option | Complexity | Infrastructure |
|--------|-----------|---------------|
| GCP Cloud Tasks (recommended) | Low | Managed, no servers |
| Redis + Celery | Medium | Requires Redis instance |
| asyncio.Semaphore + gather | Low | In-process, no persistence |

**GCP Cloud Tasks** is simplest — push "provision user X" to queue,
worker processes with configurable concurrency (e.g., 50 concurrent).
Failed tasks auto-retry. No infrastructure to manage.

With 50 concurrent provisions: 1000 users in ~15 minutes.

### 2. GCP Quota Increase

Request via GCP console before any launch:
```
gcloud compute project-info describe --project=agent-explorer-app
# Check: INSTANCES quota per region
# Request increase to 1000+ via console
```
Takes 1-2 business days. Must be done before launch.

### 3. Multi-Zone Distribution

Round-robin across 3-4 zones to avoid single-zone capacity:
```
zones = ["us-central1-a", "us-central1-b", "us-central1-c", "us-central1-f"]
zone = zones[user_count % len(zones)]
```

~5 lines of code change in provision.py.

### 4. Backend Horizontal Scaling

Run 3-4 FastAPI instances behind GCP Cloud Run or a load balancer.
Backend is stateless (SQLite → switch to PostgreSQL for concurrent
writes from multiple instances).

SQLite → PostgreSQL migration is the main effort here (~2 hours).

## Implementation Order

1. Request GCP quota increase (manual, 1-2 days lead time)
2. Multi-zone provisioning (5 lines)
3. Cloud Tasks queue (replace BackgroundTasks, ~50 lines)
4. PostgreSQL migration (if running multiple backend instances)

## When to Implement

Before any launch that could bring >50 signups/day. The current
architecture handles ~50-100 users/day comfortably. Beyond that,
Stage 7 is required.
