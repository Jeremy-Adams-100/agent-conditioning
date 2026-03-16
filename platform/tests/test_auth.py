"""Tests for auth endpoints: signup, login, logout."""


def test_signup_success(client):
    r = client.post("/api/auth/signup", json={
        "email": "test@example.com", "password": "testpass123"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "test@example.com"
    assert "user_id" in data
    assert "session" in r.cookies


def test_signup_duplicate_email(client):
    client.post("/api/auth/signup", json={
        "email": "dup@example.com", "password": "testpass123"
    })
    r = client.post("/api/auth/signup", json={
        "email": "dup@example.com", "password": "testpass123"
    })
    assert r.status_code == 409


def test_signup_short_password(client):
    r = client.post("/api/auth/signup", json={
        "email": "short@example.com", "password": "short"
    })
    assert r.status_code == 400


def test_signup_bad_email(client):
    r = client.post("/api/auth/signup", json={
        "email": "not-an-email", "password": "testpass123"
    })
    assert r.status_code == 400


def test_login_success(client):
    client.post("/api/auth/signup", json={
        "email": "login@example.com", "password": "testpass123"
    })
    r = client.post("/api/auth/login", json={
        "email": "login@example.com", "password": "testpass123"
    })
    assert r.status_code == 200
    assert r.json()["email"] == "login@example.com"
    assert "session" in r.cookies


def test_login_wrong_password(client):
    client.post("/api/auth/signup", json={
        "email": "wrong@example.com", "password": "testpass123"
    })
    r = client.post("/api/auth/login", json={
        "email": "wrong@example.com", "password": "wrongpassword"
    })
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = client.post("/api/auth/login", json={
        "email": "nobody@example.com", "password": "testpass123"
    })
    assert r.status_code == 401


def test_logout(client):
    r = client.post("/api/auth/signup", json={
        "email": "logout@example.com", "password": "testpass123"
    })
    r = client.post("/api/auth/logout", cookies=r.cookies)
    assert r.status_code == 204


def test_protected_endpoint_without_cookie(client):
    r = client.get("/api/onboard/status")
    assert r.status_code == 401
