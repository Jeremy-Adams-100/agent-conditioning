"""VM provisioning — creates a GCP VM for a user after onboarding completes."""

import asyncio
import secrets

import httpx

from explorer_platform import config, gcp
from explorer_platform.crypto import decrypt
from explorer_platform.db import get_user_by_id, update_user_field
from explorer_platform.deps import get_db

# Polling config (short in mock mode, longer for real GCP)
_POLL_ATTEMPTS = 3 if config.GCP_MOCK else 30
_POLL_INTERVAL = 0.1 if config.GCP_MOCK else 2


async def provision_vm(user_id: str) -> None:
    """Create a VM for the user, inject credentials, wait for agent readiness.

    Called as a BackgroundTask after both Claude and Wolfram credentials are linked.
    """
    conn = get_db()
    user = get_user_by_id(conn, user_id)
    if not user:
        return

    # Don't re-provision if VM already exists
    if user.get("vm_id"):
        return

    update_user_field(conn, user_id, "vm_status", "provisioning")

    vm_agent_token = secrets.token_hex(32)
    vm_name = f"explorer-{user_id[:8]}"

    try:
        result = await gcp.create_vm(
            name=vm_name,
            metadata={
                "vm-agent-token": vm_agent_token,
                "claude-token": decrypt(user["claude_token"]) if user["claude_token"] else "",
                "wolfram-key": decrypt(user["wolfram_key"]) if user["wolfram_key"] else "",
                "tier": user["tier"] or "unknown",
            },
        )

        update_user_field(conn, user_id, "vm_id", result["name"])
        update_user_field(conn, user_id, "vm_zone", result["zone"])
        update_user_field(conn, user_id, "vm_internal_ip", result["internal_ip"])
        update_user_field(conn, user_id, "vm_agent_token", vm_agent_token)

        # Poll until VM agent responds
        agent_url = f"http://{result['internal_ip']}:{config.VM_AGENT_PORT}"
        ready = False
        async with httpx.AsyncClient(timeout=5.0) as client:
            for _ in range(_POLL_ATTEMPTS):
                try:
                    r = await client.get(
                        f"{agent_url}/status",
                        headers={"Authorization": f"Bearer {vm_agent_token}"},
                    )
                    if r.status_code == 200:
                        ready = True
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                await asyncio.sleep(_POLL_INTERVAL)

        if ready or config.GCP_MOCK:
            # In mock mode, mark ready immediately (no real agent to poll)
            update_user_field(conn, user_id, "vm_status", "ready")
        else:
            update_user_field(conn, user_id, "vm_status", "provision_failed")

    except Exception:
        from explorer_platform.log import logger
        logger.exception(f"VM provisioning failed for user {user_id[:8]}")
        update_user_field(conn, user_id, "vm_status", "provision_failed")
