"""
conftest.py — Shared pytest fixtures for all backend tests.

Provides:
  - client: session-scoped TestClient against the real DB (anonymous)
             (required for E2E tests: worker uses SessionLocal directly)
  - client_authed: session-scoped TestClient against the real DB with auth bypass
                   (for E2E/integration/WebSocket tests after Task 10)
  - isolated_client: function-scoped TestClient with in-memory DB override
                     (for fast unit/download tests that must not touch real DB)
  - isolated_client_authed: same as isolated_client but with auth bypass
                            (for download tests after Task 10)
  - auth_client: function-scoped authenticated TestClient (User A / TenantA)
  - auth_client_b: User B auth headers dict (shares DB with auth_client)
  - test_engine / test_db: in-memory SQLite engine + isolated session for
                           tests that interact with the DB directly
  - GTFS_ZIP / EXPECTED_CSVS: shared path/list constants
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend package is importable when pytest is run from backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.db.database import Base, engine as real_engine, get_db
from sqlalchemy.pool import StaticPool as _StaticPool

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────

GTFS_ZIP = Path(__file__).parent / "Resources" / "raw" / "SEM-GTFS(2).zip"

EXPECTED_CSVS = [
    "A_1_Arrets_Generiques.csv",
    "A_2_Arrets_Physiques.csv",
    "B_1_Lignes.csv",
    "B_2_Sous_Lignes.csv",
    "C_1_Courses.csv",
    "C_2_Itineraire.csv",
    "C_3_Itineraire_Arc.csv",
    "D_1_Service_Dates.csv",
    "D_2_Service_Jourtype.csv",
    "E_1_Nombre_Passage_AG.csv",
    "E_4_Nombre_Passage_Arc.csv",
    "F_1_Nombre_Courses_Lignes.csv",
    "F_2_Caract_SousLignes.csv",
    "F_3_KCC_Lignes.csv",
    "F_4_KCC_Sous_Ligne.csv",
]

# ──────────────────────────────────────────────────────────────────
# Real-DB client (session-scoped) — for E2E / integration tests
#
# Worker accesses the DB via SessionLocal (not the FastAPI get_db
# dependency), so both the API and the worker must share the same
# physical DB file.  Using the real engine ensures this.
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """Session-scoped TestClient against the real SQLite DB.

    Use this fixture in integration / E2E tests where the background
    worker must be able to read/write the same project rows that the
    API created.
    """
    Base.metadata.create_all(bind=real_engine)
    with TestClient(app) as c:
        yield c


# ──────────────────────────────────────────────────────────────────
# In-memory DB fixtures — for isolated unit / download tests
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    """In-memory SQLite engine shared across the test session.

    StaticPool forces all sessions to reuse the same underlying connection,
    which is required for SQLite in-memory mode: without it each new
    connection gets its own empty database, making cross-session data
    invisible.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine):
    """Isolated DB session: yields session, rolls back after each test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def isolated_client(test_engine):
    """Function-scoped TestClient with get_db overridden to use in-memory DB.

    Use this fixture in fast unit tests (download, error-case, etc.) that
    must not touch the real DB and do not run the background worker.
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fresh_client():
    """Function-scoped TestClient with a brand-new in-memory DB.

    Use this for auth tests that INSERT rows and need full isolation
    between test functions (no shared state from other tests).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=_StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    FreshSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = FreshSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


# ──────────────────────────────────────────────────────────────────
# Auth-aware fixtures (Task 10+)
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def auth_client(fresh_client):
    """Authenticated TestClient — User A (TenantA).

    Registers alice@test.com and sets the Authorization header on the
    shared fresh_client.  auth_client_b, if requested in the same test,
    shares the same underlying in-memory DB.
    """
    r = fresh_client.post("/api/v1/auth/register", json={
        "email": "alice@test.com",
        "password": "password123",
        "tenant_name": "TenantA",
    })
    assert r.status_code == 201, f"auth_client setup failed: {r.text}"
    token = r.json()["access_token"]
    fresh_client.headers.update({"Authorization": f"Bearer {token}"})
    return fresh_client


@pytest.fixture
def auth_client_b(fresh_client):
    """Auth headers for User B (TenantB) — dict, not a client.

    Shares the same in-memory DB as auth_client when both are requested
    by the same test (pytest reuses the function-scoped fresh_client
    instance within a single test).

    Usage::
        def test_isolation(auth_client, auth_client_b):
            auth_client.get("/api/v1/projects/", headers=auth_client_b)
    """
    r = fresh_client.post("/api/v1/auth/register", json={
        "email": "bob@test.com",
        "password": "password456",
        "tenant_name": "TenantB",
    })
    assert r.status_code == 201, f"auth_client_b setup failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def client_authed():
    """Session-scoped TestClient against the real DB with auth bypassed.

    Use this in E2E / integration / WebSocket tests that need the real
    background worker but do not test authentication itself.
    get_current_active_user is overridden to return a stable fake User so
    all project-endpoint calls are authenticated without a real login flow.
    """
    from app.api.deps import get_current_active_user
    from app.db.models import User

    fake_user = User(
        id="test-user-id",
        email="test@test.com",
        hashed_password="irrelevant",
        tenant_id="test-tenant-id",
        is_active=True,
        role="admin",
    )
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    Base.metadata.create_all(bind=real_engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.fixture
def isolated_client_authed(test_engine):
    """Function-scoped in-memory TestClient with auth bypassed.

    Like isolated_client but also overrides get_current_active_user so
    project endpoints (protected since Task 10) can be called without a
    real JWT token.  Use this for download / error-case tests.
    """
    from app.api.deps import get_current_active_user
    from app.db.models import User

    fake_user = User(
        id="test-user-id",
        email="test@test.com",
        hashed_password="irrelevant",
        tenant_id="test-tenant-id",
        is_active=True,
        role="admin",
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
