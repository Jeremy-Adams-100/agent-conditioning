"""Platform configuration from environment variables."""

import os
from pathlib import Path

# Required secrets (validated at startup in app.py lifespan)
FERNET_KEY: str = os.environ.get("PLATFORM_FERNET_KEY", "")
COOKIE_SECRET: str = os.environ.get("PLATFORM_COOKIE_SECRET", "")

# Database
DB_PATH: Path = Path(os.environ.get(
    "PLATFORM_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "users.db"),
))

# Cookie settings
COOKIE_NAME: str = "session"
COOKIE_MAX_AGE: int = 60 * 60 * 24 * 30  # 30 days

# Server
HOST: str = os.environ.get("PLATFORM_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("PLATFORM_PORT", "8000"))

# GCP Compute Engine
GCP_PROJECT: str = os.environ.get("GCP_PROJECT", "")
GCP_ZONE: str = os.environ.get("GCP_ZONE", "us-central1-a")
GCP_BASE_IMAGE: str = os.environ.get("GCP_BASE_IMAGE", "agent-explorer-base-v4")
GCP_MACHINE_TYPE: str = os.environ.get("GCP_MACHINE_TYPE", "e2-medium")
GCP_MOCK: bool = os.environ.get("GCP_MOCK", "true").lower() == "true"
VM_AGENT_PORT: int = int(os.environ.get("VM_AGENT_PORT", "8080"))
