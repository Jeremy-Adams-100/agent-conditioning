"""Onboarding endpoints: Claude token linking, Wolfram key linking, status."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from explorer_platform.crypto import encrypt
from explorer_platform.db import update_user_field
from explorer_platform.deps import get_current_user, get_db

router = APIRouter(prefix="/api/onboard", tags=["onboard"])


class ClaudeTokenRequest(BaseModel):
    claude_token: str


class WolframKeyRequest(BaseModel):
    wolfram_key: str


@router.post("/claude")
def link_claude(body: ClaudeTokenRequest, user=Depends(get_current_user),
                conn=Depends(get_db)):
    if not body.claude_token.strip():
        raise HTTPException(400, "Token cannot be empty")

    encrypted = encrypt(body.claude_token.strip())
    update_user_field(conn, user["id"], "claude_token", encrypted)

    return {"status": "linked", "tier": "unknown"}


@router.post("/wolfram")
def link_wolfram(body: WolframKeyRequest, user=Depends(get_current_user),
                 conn=Depends(get_db)):
    if not body.wolfram_key.strip():
        raise HTTPException(400, "Key cannot be empty")

    encrypted = encrypt(body.wolfram_key.strip())
    update_user_field(conn, user["id"], "wolfram_key", encrypted)

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
