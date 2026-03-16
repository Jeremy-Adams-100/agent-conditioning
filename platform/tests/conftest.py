"""Shared test fixtures."""

import os

from cryptography.fernet import Fernet

# Set env vars before any app imports
os.environ["PLATFORM_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["PLATFORM_COOKIE_SECRET"] = "test-cookie-secret"
os.environ["PLATFORM_DB_PATH"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

from explorer_platform.app import app


@pytest.fixture()
def client():
    """TestClient with lifespan (DB init) triggered via context manager."""
    with TestClient(app) as c:
        yield c
