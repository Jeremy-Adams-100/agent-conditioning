"""Email verification: send verification link, verify token."""

import smtplib
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from itsdangerous import BadSignature, URLSafeTimedSerializer

from explorer_platform import config
from explorer_platform.db import update_user_field
from explorer_platform.deps import get_current_user, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

_VERIFY_MAX_AGE = 60 * 60 * 24  # 24 hours


def _get_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.COOKIE_SECRET, salt="email-verify")


def send_verification_email(email: str, user_id: str) -> bool:
    """Send a verification email. Returns False if SMTP is not configured."""
    if not config.SMTP_HOST:
        return False

    token = _get_signer().dumps(user_id)
    # In production, this URL would use the real domain
    verify_url = f"http://localhost:3000/api/auth/verify-email?token={token}"

    body = (
        f"Welcome to Q.E.D.\n\n"
        f"Click the link below to verify your email:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in 24 hours."
    )

    msg = MIMEText(body)
    msg["Subject"] = "Verify your Q.E.D. account"
    msg["From"] = config.SMTP_FROM
    msg["To"] = email

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        return False


@router.get("/verify-email")
def verify_email(token: str, conn=Depends(get_db)):
    """Verify email via signed token link."""
    try:
        user_id = _get_signer().loads(token, max_age=_VERIFY_MAX_AGE)
    except BadSignature:
        raise HTTPException(400, "Invalid or expired verification link")

    update_user_field(conn, user_id, "email_verified", 1)
    return {"status": "verified"}


@router.post("/resend-verification")
def resend_verification(user=Depends(get_current_user)):
    """Resend verification email to the current user."""
    if user.get("email_verified"):
        return {"status": "already_verified"}

    sent = send_verification_email(user["email"], user["id"])
    if not sent:
        raise HTTPException(503, "Email service not configured")
    return {"status": "sent"}
