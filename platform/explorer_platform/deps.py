"""FastAPI dependencies: database connection + auth."""

import sqlite3

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from explorer_platform import config
from explorer_platform.db import get_user_by_id

# Module-level connection (set during app lifespan)
_conn: sqlite3.Connection | None = None
_signer: URLSafeTimedSerializer | None = None


def set_conn(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def get_db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized")
    return _conn


def get_signer() -> URLSafeTimedSerializer:
    global _signer
    if _signer is None:
        if not config.COOKIE_SECRET:
            raise RuntimeError("PLATFORM_COOKIE_SECRET not set")
        _signer = URLSafeTimedSerializer(config.COOKIE_SECRET)
    return _signer


def sign_user_id(user_id: str) -> str:
    """Sign a user ID for cookie storage."""
    return get_signer().dumps(user_id)


def get_current_user(request: Request) -> dict:
    """Extract and validate the session cookie. Returns user dict or raises 401."""
    cookie = request.cookies.get(config.COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = get_signer().loads(cookie, max_age=config.COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = get_user_by_id(get_db(), user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
