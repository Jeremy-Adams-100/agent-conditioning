"""Background task: suspend idle VMs to save cost."""

from datetime import datetime, timezone

import httpx

from explorer_platform import config, gcp
from explorer_platform.db import update_user_field
from explorer_platform.deps import get_db
from explorer_platform.vm_client import VMClient


async def check_idle_vms() -> None:
    """Suspend VMs that have been idle for over 1 hour."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, vm_id, vm_zone, vm_internal_ip, vm_agent_token "
        "FROM users WHERE vm_status = 'running'"
    ).fetchall()

    for row in rows:
        user = dict(row)
        try:
            client = VMClient(
                base_url=f"http://{user['vm_internal_ip']}:{config.VM_AGENT_PORT}",
                token=user["vm_agent_token"],
            )
            status = await client.get_status()

            # If exploration is actively running, skip
            if status.get("exploration_running"):
                continue

            # Check timestamp from state
            state = status.get("state", {})
            ts = state.get("timestamp", "")
            if ts and _older_than_hours(ts, 1):
                await gcp.suspend_vm(user["vm_zone"], user["vm_id"])
                update_user_field(conn, user["id"], "vm_status", "suspended")

        except Exception:
            pass  # VM unreachable — skip this check


def _older_than_hours(iso_timestamp: str, hours: int) -> bool:
    """Check if an ISO timestamp is older than N hours from now."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        return age > hours * 3600
    except (ValueError, TypeError):
        return True  # Can't parse → treat as old
