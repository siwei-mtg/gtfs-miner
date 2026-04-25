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


def test_me_returns_plan_free_by_default(fresh_client):
    """Task 40A: /auth/me exposes the tenant's plan so the frontend can gate
    premium features.  New tenants default to the 'free' plan (see Tenant
    model).  Frontend usePlan() reads this."""
    token = _register(fresh_client).json()["access_token"]
    r = fresh_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "plan" in body
    assert body["plan"] == "free"


def test_me_returns_plan_pro_when_tenant_upgraded(fresh_client):
    """Upgrade the tenant directly in the DB (simulating an admin upgrade
    flow not yet in scope), then confirm /auth/me reflects the new plan."""
    from app.db.models import Tenant, User
    from app.db.database import SessionLocal  # noqa: F401 — imported for side-effect path

    token = _register(fresh_client).json()["access_token"]
    # Reach into the fresh_client's in-memory DB via the dependency override.
    from app.db.database import get_db
    from app.main import app
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        user = db.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).first()
        assert user is not None
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        assert tenant is not None
        tenant.plan = "pro"
        db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    r = fresh_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["plan"] == "pro"


def test_me_no_token(fresh_client):
    r = fresh_client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_invalid_token(fresh_client):
    r = fresh_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


# ── project endpoint auth guards (Task 10) ────────────────────────────────────

def test_create_project_unauthenticated(fresh_client):
    """POST /projects without a token must return 401."""
    r = fresh_client.post("/api/v1/projects", json={})
    assert r.status_code == 401


def test_create_project_authenticated(auth_client):
    """POST /projects with a valid token must return 201."""
    r = auth_client.post("/api/v1/projects", json={})
    assert r.status_code == 201


def test_list_projects_only_own_tenant(auth_client, auth_client_b):
    """User B must not see projects created by User A (different tenant)."""
    # A creates a project
    auth_client.post("/api/v1/projects", json={})
    # B lists projects — auth_client_b headers override A's session header
    r = auth_client.get("/api/v1/projects", headers=auth_client_b)
    assert r.json() == []
