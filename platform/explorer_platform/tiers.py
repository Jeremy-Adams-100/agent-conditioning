"""Tier detection and configuration.

Detects whether a user's Claude account supports opus (Max plan)
or only sonnet (Free plan) by calling the VM agent's /detect-tier endpoint.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from explorer_platform import config
from explorer_platform.db import update_user_field
from explorer_platform.deps import get_current_user, get_db
from explorer_platform.vm_client import get_vm_client

router = APIRouter(prefix="/api/tier", tags=["tier"])

# Tier definitions
TIERS = {
    "free": {
        "model": "sonnet",
        "context_window": 200_000,
        "cycle_cooldown_seconds": 120,
    },
    "max": {
        "model": "opus",
        "context_window": 1_000_000,
        "cycle_cooldown_seconds": 30,
    },
}


@router.post("/check")
async def check_tier(user=Depends(get_current_user), conn=Depends(get_db)):
    """Detect the user's Claude tier by testing opus access on their VM.

    Requires VM to be provisioned and running.
    """
    if not user.get("vm_internal_ip") or not user.get("vm_agent_token"):
        raise HTTPException(409, "VM not provisioned")

    client = get_vm_client(user)
    try:
        result = await client._client.get("/detect-tier")
        result.raise_for_status()
        data = result.json()
        tier = data.get("tier", "free")
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        raise HTTPException(502, "Could not reach VM to detect tier")

    # Update tier in database
    if tier in TIERS:
        update_user_field(conn, user["id"], "tier", tier)

    return {"tier": tier, "config": TIERS.get(tier, TIERS["free"])}
