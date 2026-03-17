"""Auth endpoints: signup, login, logout."""

import re
import sqlite3
import uuid
from datetime import datetime, timezone

import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from explorer_platform import config
from explorer_platform.db import create_user, get_user_by_email
from explorer_platform.deps import get_current_user, get_db, sign_user_id

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    email: str
    password: str
    turnstile_token: str = ""  # optional — required only when Turnstile is configured


class AuthRequest(BaseModel):
    email: str
    password: str


async def _verify_turnstile(token: str) -> bool:
    """Verify Cloudflare Turnstile token. Returns True if valid or if Turnstile is disabled."""
    if not config.TURNSTILE_SECRET_KEY:
        return True  # Turnstile not configured — skip
    if not token:
        return False
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": config.TURNSTILE_SECRET_KEY, "response": token},
        )
        return r.json().get("success", False)


def _set_session_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        key=config.COOKIE_NAME,
        value=sign_user_id(user_id),
        max_age=config.COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


@router.post("/signup")
async def signup(body: SignupRequest, response: Response, conn=Depends(get_db)):
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(400, "Invalid email format")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    # CAPTCHA verification
    if not await _verify_turnstile(body.turnstile_token):
        raise HTTPException(400, "CAPTCHA verification failed")

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        create_user(conn, user_id, body.email, password_hash, created_at)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")

    # Send verification email (non-blocking — don't fail signup if email fails)
    from explorer_platform.email_verify import send_verification_email
    send_verification_email(body.email, user_id)

    _set_session_cookie(response, user_id)
    return {"user_id": user_id, "email": body.email}


@router.post("/login")
def login(body: AuthRequest, response: Response, conn=Depends(get_db)):
    user = get_user_by_email(conn, body.email)
    if not user:
        raise HTTPException(401, "Invalid credentials")

    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")

    _set_session_cookie(response, user["id"])
    return {"user_id": user["id"], "email": user["email"]}


@router.post("/logout", status_code=204)
def logout(response: Response, _user=Depends(get_current_user)):
    response.delete_cookie(key=config.COOKIE_NAME, path="/")


@router.get("/turnstile-key")
def get_turnstile_key():
    """Return the Turnstile site key for the frontend (public, no auth needed)."""
    return {"site_key": config.TURNSTILE_SITE_KEY}
