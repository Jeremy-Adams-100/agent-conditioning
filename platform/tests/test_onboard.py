"""Tests for onboarding endpoints: Claude/Wolfram linking, status."""


def _signup(client, email="onboard@example.com"):
    """Helper: sign up and return cookies."""
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "testpass123"
    })
    return r.cookies


def test_status_nothing_linked(client):
    cookies = _signup(client, "status1@example.com")
    r = client.get("/api/onboard/status", cookies=cookies)
    assert r.status_code == 200
    data = r.json()
    assert data["claude_linked"] is False
    assert data["wolfram_linked"] is False
    assert data["onboarding_complete"] is False
    assert data["tier"] == "unknown"
    assert data["vm_status"] == "none"


def test_link_claude_token(client):
    cookies = _signup(client, "claude1@example.com")
    r = client.post("/api/onboard/claude", json={
        "claude_token": "sk-ant-test-token-123"
    }, cookies=cookies)
    assert r.status_code == 200
    assert r.json()["status"] == "linked"
    assert r.json()["tier"] == "unknown"

    r = client.get("/api/onboard/status", cookies=cookies)
    assert r.json()["claude_linked"] is True
    assert r.json()["onboarding_complete"] is False


def test_link_wolfram_key(client):
    cookies = _signup(client, "wolfram1@example.com")
    r = client.post("/api/onboard/wolfram", json={
        "wolfram_key": "1234-5678-ABCDEF"
    }, cookies=cookies)
    assert r.status_code == 200
    assert r.json()["status"] == "linked"


def test_onboarding_complete(client):
    cookies = _signup(client, "complete@example.com")
    client.post("/api/onboard/claude", json={
        "claude_token": "token"
    }, cookies=cookies)
    client.post("/api/onboard/wolfram", json={
        "wolfram_key": "key"
    }, cookies=cookies)

    r = client.get("/api/onboard/status", cookies=cookies)
    data = r.json()
    assert data["claude_linked"] is True
    assert data["wolfram_linked"] is True
    assert data["onboarding_complete"] is True


def test_link_empty_token_rejected(client):
    cookies = _signup(client, "empty1@example.com")
    r = client.post("/api/onboard/claude", json={
        "claude_token": "  "
    }, cookies=cookies)
    assert r.status_code == 400


def test_link_empty_key_rejected(client):
    cookies = _signup(client, "empty2@example.com")
    r = client.post("/api/onboard/wolfram", json={
        "wolfram_key": ""
    }, cookies=cookies)
    assert r.status_code == 400
