"""Auth endpoints: signup, login, logout."""

import re
import sqlite3
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from explorer_platform import config
from explorer_platform.db import create_user, get_user_by_email
from explorer_platform.deps import get_current_user, get_db, sign_user_id

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthRequest(BaseModel):
    email: str
    password: str


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
def signup(body: AuthRequest, response: Response, conn=Depends(get_db)):
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(400, "Invalid email format")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        create_user(conn, user_id, body.email, password_hash, created_at)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")

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
