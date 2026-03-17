"""Tests for Stage 2: VM provisioning, exploration control, data proxy."""

import time


def _signup_and_onboard(client, email="stage2@example.com"):
    """Helper: sign up, link both credentials, wait for provisioning."""
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "testpass123"
    })
    cookies = r.cookies
    client.post("/api/onboard/claude", json={
        "claude_token": "test-token"
    }, cookies=cookies)
    client.post("/api/onboard/wolfram", json={
        "wolfram_key": "test-key"
    }, cookies=cookies)

    # Wait briefly for background provisioning (mock is fast)
    time.sleep(0.5)

    return cookies


# --- Provisioning ---

def test_provisioning_triggered_on_onboard_complete(client):
    cookies = _signup_and_onboard(client, "provision@example.com")
    r = client.get("/api/onboard/status", cookies=cookies)
    data = r.json()
    assert data["onboarding_complete"] is True
    assert data["vm_status"] in ("ready", "provisioning")


def test_provisioning_sets_vm_fields(client):
    cookies = _signup_and_onboard(client, "vmfields@example.com")
    time.sleep(0.5)
    r = client.get("/api/onboard/status", cookies=cookies)
    data = r.json()
    # In mock mode, VM should be ready immediately
    assert data["vm_status"] == "ready"


# --- Exploration control (without real VM agent, expect 502 or connection errors) ---

def test_explore_start_without_onboarding(client):
    r = client.post("/api/auth/signup", json={
        "email": "noonboard@example.com", "password": "testpass123"
    })
    r = client.post("/api/explore/start", json={"topic": "test"},
                    cookies=r.cookies)
    assert r.status_code == 409  # VM not provisioned


def test_explore_stop_without_vm(client):
    r = client.post("/api/auth/signup", json={
        "email": "nostop@example.com", "password": "testpass123"
    })
    r = client.post("/api/explore/stop", cookies=r.cookies)
    assert r.status_code == 409  # VM not provisioned


# --- Data proxy (without real VM agent) ---

def test_proxy_status_without_vm(client):
    r = client.post("/api/auth/signup", json={
        "email": "noproxy@example.com", "password": "testpass123"
    })
    r = client.get("/api/data/status", cookies=r.cookies)
    assert r.status_code == 200  # graceful default when VM unreachable
    assert r.json()["exploration_running"] is False


def test_proxy_files_without_vm(client):
    r = client.post("/api/auth/signup", json={
        "email": "nofiles@example.com", "password": "testpass123"
    })
    r = client.get("/api/data/files", cookies=r.cookies)
    assert r.status_code == 200
    assert r.json() == []


# --- Auth required for all new endpoints ---

def test_explore_requires_auth(client):
    r = client.post("/api/explore/start", json={"topic": "test"})
    assert r.status_code == 401


def test_proxy_requires_auth(client):
    r = client.get("/api/data/status")
    assert r.status_code == 401


# --- GCP mock layer ---

def test_mock_gcp_create_and_info(client):
    import asyncio
    from explorer_platform.gcp import create_vm, get_vm_info, suspend_vm, resume_vm

    async def _test():
        result = await create_vm("test-vm", {"key": "value"})
        assert result["name"] == "test-vm"
        assert result["internal_ip"].startswith("10.128.0.")

        info = await get_vm_info(result["zone"], "test-vm")
        assert info["status"] == "RUNNING"

        await suspend_vm(result["zone"], "test-vm")
        info = await get_vm_info(result["zone"], "test-vm")
        assert info["status"] == "SUSPENDED"

        await resume_vm(result["zone"], "test-vm")
        info = await get_vm_info(result["zone"], "test-vm")
        assert info["status"] == "RUNNING"

    asyncio.run(_test())
