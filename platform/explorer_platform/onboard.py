"""Onboarding endpoints: Claude token linking, Wolfram key linking, status."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from explorer_platform.crypto import encrypt
from explorer_platform.db import get_user_by_id, update_user_field
from explorer_platform.deps import get_current_user, get_db
from explorer_platform.provision import provision_vm

router = APIRouter(prefix="/api/onboard", tags=["onboard"])


class ClaudeTokenRequest(BaseModel):
    claude_token: str


class WolframKeyRequest(BaseModel):
    wolfram_key: str


def _maybe_provision(user_id: str, conn, bg: BackgroundTasks) -> None:
    """Trigger VM provisioning if both credentials are linked and no VM exists."""
    user = get_user_by_id(conn, user_id)
    if not user:
        return
    if (user["claude_token"] and user["wolfram_key"]
            and (user["vm_status"] or "none") == "none"):
        bg.add_task(provision_vm, user_id)


@router.post("/claude")
def link_claude(body: ClaudeTokenRequest, bg: BackgroundTasks,
                user=Depends(get_current_user), conn=Depends(get_db)):
    if not body.claude_token.strip():
        raise HTTPException(400, "Token cannot be empty")

    encrypted = encrypt(body.claude_token.strip())
    update_user_field(conn, user["id"], "claude_token", encrypted)

    _maybe_provision(user["id"], conn, bg)

    return {"status": "linked", "tier": "unknown"}


@router.post("/wolfram")
def link_wolfram(body: WolframKeyRequest, bg: BackgroundTasks,
                 user=Depends(get_current_user), conn=Depends(get_db)):
    if not body.wolfram_key.strip():
        raise HTTPException(400, "Key cannot be empty")

    encrypted = encrypt(body.wolfram_key.strip())
    update_user_field(conn, user["id"], "wolfram_key", encrypted)

    _maybe_provision(user["id"], conn, bg)

    return {"status": "linked"}


@router.get("/status")
def onboard_status(user=Depends(get_current_user)):
    return {
        "email": user["email"],
        "tier": user["tier"],
        "claude_linked": user["claude_token"] is not None,
        "wolfram_linked": user["wolfram_key"] is not None,
        "vm_status": user["vm_status"] or "none",
        "onboarding_complete": (
            user["claude_token"] is not None
            and user["wolfram_key"] is not None
        ),
    }
