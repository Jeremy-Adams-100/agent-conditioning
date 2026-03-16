# VM Provider Comparison

## Our Requirements

- Per-user isolated VM (2 vCPU, 4GB RAM, 20GB disk)
- API-driven provisioning (create/start/stop/destroy)
- Low cost when idle (most users idle most of the time)
- Reliable enough for research workloads (not mission-critical)
- Simple integration (REST API, not enterprise complexity)
- Pre-built images (clone a base image per user)

## Provider Comparison

| | Fly.io | Hetzner | AWS EC2 | GCP Compute | DigitalOcean |
|---|---|---|---|---|---|
| **Running cost** (2vCPU/4GB) | ~$31/mo | ~€8/mo (~$9) | ~$30/mo | ~$25/mo | ~$24/mo |
| **Idle cost** | $0.15/GB rootfs (~$3/mo) | Full price (must destroy to stop billing) | EBS only (~$2/mo) | Disk only (~$0.80/mo) | Full price (must destroy) |
| **Native suspend/resume** | Yes (memory preserved) | No (stop/start = cold boot) | Limited (hibernation for some types) | Yes | No |
| **Provisioning speed** | Seconds | Seconds | 30-60s | 30-60s | Seconds |
| **API quality** | Excellent, modern | Good, simple REST | Comprehensive, complex | Comprehensive, complex | Excellent, simple |
| **Uptime SLA** | None formal | 99.9% (no formal SLA) | 99.99% | 99.99% | 99.99% |
| **Reliability record** | Concerning (1,596 outages in 5yr, IAD dependency) | Solid (own hardware, since 1997) | Industry standard | Industry standard | Strong (99.99% observed) |
| **Regions** | 30+ worldwide | EU + US (limited) | 30+ | 35+ | 15 |
| **Company maturity** | Startup (2017) | Established (1997) | Enterprise (2006) | Enterprise (2008) | Established (2011) |
| **Base image support** | Docker images | Snapshots | AMIs | Machine images | Snapshots |
| **Security/trust** | Moderate | High (German data privacy) | Highest | Highest | High |
| **Free tier** | $0 stopped machines | None | 750hr t2.micro/yr | 1 e2-micro always free | None |
| **Billing granularity** | Per second | Per hour | Per second | Per second | Per second |

## Cost Model: 1,000 Users (10% Active)

Assumes 100 users running at any time, 900 idle.

| Provider | Running (100 VMs) | Idle (900 VMs) | Monthly Total | Notes |
|---|---|---|---|---|
| **Fly.io** | $3,100 | $2,700 (rootfs storage) | **~$5,800** | Suspend = cheapest idle cost |
| **Hetzner** | $900 | $0 (destroy + snapshot) | **~$1,100** | Must destroy/recreate on resume. Snapshot storage ~$200 |
| **AWS EC2** | $3,000 | $1,800 (EBS storage) | **~$4,800** | Stop = free compute, pay EBS |
| **GCP** | $2,500 | $720 (disk storage) | **~$3,200** | Suspend available. Cheapest major cloud |
| **DigitalOcean** | $2,400 | $21,600 (no stop savings) | **~$24,000** | Must destroy/recreate, or pay full price idle |

## Cost Model: 100 Users (20% Active)

Assumes 20 users running at any time, 80 idle.

| Provider | Running (20 VMs) | Idle (80 VMs) | Monthly Total | Notes |
|---|---|---|---|---|
| **Fly.io** | $620 | $240 | **~$860** | |
| **Hetzner** | $180 | $20 (snapshots) | **~$200** | |
| **AWS EC2** | $600 | $160 | **~$760** | |
| **GCP** | $500 | $64 | **~$564** | |
| **DigitalOcean** | $480 | $1,920 | **~$2,400** | (if no destroy/recreate) |

## Assessment

### Fly.io
**Pros:** Best suspend/resume (memory preserved, instant wake), modern API, Docker-native, zero cost stopped machines.
**Cons:** Reliability is a real concern — 1,596 outages tracked, ~6hr average resolution. Their API depends on a single region (IAD). Startup risk. Suspended machines still cost $0.15/GB/month for rootfs.
**Verdict:** Best developer experience but a reliability gamble for a platform serving paying users.

### Hetzner
**Pros:** By far the cheapest running cost (~$9/mo per VM). Own hardware, established company, excellent price/performance. Simple API.
**Cons:** No suspend — must destroy and recreate from snapshots (adds 10-30s resume latency). Limited regions (EU + US). No formal SLA. Price increase coming April 2026 (~30%).
**Verdict:** Best value if resume latency is acceptable. The destroy/recreate pattern is more work but saves the most money at scale.

### AWS EC2
**Pros:** Industry standard reliability. Most regions. Best ecosystem (IAM, VPC, CloudWatch). Enterprise trust.
**Cons:** Most expensive running cost. Most complex API. Stop preserves EBS but no memory suspend. Over-engineering risk — easy to get lost in AWS services.
**Verdict:** The safe enterprise choice. Overkill for early stage but the right answer if the platform reaches significant scale.

### GCP Compute Engine
**Pros:** True suspend/resume support. Cheapest idle cost ($0.04/GB/month disk). Strong free tier (1 e2-micro always free). 99.99% SLA. Competitive running cost.
**Cons:** API is complex (similar to AWS). Less developer-friendly than Fly.io or DO. Google has a history of shutting down products (though GCE is core infrastructure and unlikely to be affected).
**Verdict:** Best balance of reliability, cost, and features. Suspend/resume works. Major cloud trust. Cheaper than AWS.

### DigitalOcean
**Pros:** Simplest API by far. Excellent documentation. 99.99% SLA. Strong community. Developer-friendly.
**Cons:** No stop billing — powered-off Droplets still cost full price. Must snapshot + destroy to stop billing (same as Hetzner but more expensive base). Per-second billing only since Jan 2026.
**Verdict:** Best API simplicity but the billing model is wrong for our use case (mostly-idle VMs).

## Recommendation

**Start with GCP Compute Engine. Fall back to Hetzner if cost is the overriding concern.**

GCP offers the best combination for this use case:
- Native suspend/resume (memory preserved, like Fly.io but reliable)
- Cheapest idle cost among major clouds ($0.04/GB/month disk)
- 99.99% SLA (unlike Fly.io and Hetzner)
- Free tier for development (1 e2-micro always free)
- The API is more complex than Fly.io but well-documented with client libraries in Python

If costs need to be minimized above all else (early bootstrapping), Hetzner's ~$9/mo running cost is hard to beat, and the destroy/recreate resume pattern is automatable.

**Avoid Fly.io for production** despite the great developer experience — the reliability record is not suitable for a platform where users expect their research to be running when they come back.

**Avoid DigitalOcean** — the billing model penalizes idle VMs, which is our dominant use case.

## Sources

- [Fly.io Pricing](https://fly.io/pricing/)
- [Fly.io Machine Suspend and Resume](https://fly.io/docs/reference/suspend-resume/)
- [Fly.io Community: Frequent Outages Discussion](https://community.fly.io/t/frequent-outages-is-really-demonstrating-fly-is-not-production-ready-yet/11502)
- [Hetzner Cloud Pricing](https://www.hetzner.com/cloud)
- [Hetzner Cloud Review 2026 (Better Stack)](https://betterstack.com/community/guides/web-servers/hetzner-cloud-review/)
- [Hetzner Price Adjustment April 2026](https://ubos.tech/news/hetzner-price-adjustment-updated-cloud-costs-effective-april-2026/)
- [AWS EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [GCP VM Instance Pricing](https://cloud.google.com/compute/vm-instance-pricing)
- [GCP e2-micro Pricing](https://gcloud-compute.com/e2-micro.html)
- [DigitalOcean Droplet Pricing](https://docs.digitalocean.com/products/droplets/details/pricing/)
- [DigitalOcean Pricing](https://www.digitalocean.com/pricing/droplets)
- [Railway Pricing](https://railway.com/pricing)
