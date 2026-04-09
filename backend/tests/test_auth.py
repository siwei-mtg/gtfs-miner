REGISTER_PAYLOAD = {
    "email": "alice@example.com",
    "password": "securepass",
    "tenant_name": "Acme",
}


def _register(client, payload=None):
    return client.post("/api/v1/auth/register", json=payload or REGISTER_PAYLOAD)


def _login(client, username="alice@example.com", password="securepass"):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )


# ── register ──────────────────────────────────────────────────────────────────

def test_register_success(fresh_client):
    r = _register(fresh_client)
    assert r.status_code == 201
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_register_duplicate_email(fresh_client):
    _register(fresh_client)
    r = _register(fresh_client)
    assert r.status_code == 409


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_success(fresh_client):
    _register(fresh_client)
    r = _login(fresh_client)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(fresh_client):
    _register(fresh_client)
    r = _login(fresh_client, password="wrongpass")
    assert r.status_code == 401


def test_login_unknown_email(fresh_client):
    r = _login(fresh_client, username="nobody@example.com")
    assert r.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

def test_me_authenticated(fresh_client):
    token = _register(fresh_client).json()["access_token"]
    r = fresh_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == REGISTER_PAYLOAD["email"]


def test_me_no_token(fresh_client):
    r = fresh_client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_invalid_token(fresh_client):
    r = fresh_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401
