"""
test_tenancy.py — GROUP C: Multi-tenant isolation tests (Task 11–12).

Task 11: Tenant filter on get / upload / download / table endpoints.
Task 12: Output directory uses {tenant_id}/{project_id}/output/ structure.

Fixtures:
  auth_client       — authenticated TestClient, User A (TenantA), fresh in-memory DB
  auth_client_b     — auth headers dict for User B (TenantB), same in-memory DB
  isolated_client_authed — in-memory DB client with auth bypass (fake tenant_id = "test-tenant-id")
  test_db           — SQLAlchemy session on the shared in-memory engine
"""
import shutil
import uuid

import pytest

from app.db.models import Project
from app.core.config import PROJECT_DIR

# Must match the tenant_id set on the fake_user inside isolated_client_authed (conftest.py)
FAKE_TENANT_ID = "test-tenant-id"


# ──────────────────────────────────────────────────────────────────
# Task 11: cross-tenant access returns 404
# ──────────────────────────────────────────────────────────────────

def test_project_invisible_to_other_tenant(auth_client, auth_client_b):
    """B cannot GET a project created by A — returns 404, not 403."""
    resp = auth_client.post("/api/v1/projects/", json={})
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    r = auth_client.get(f"/api/v1/projects/{project_id}", headers=auth_client_b)
    assert r.status_code == 404


def test_list_isolated(auth_client, auth_client_b):
    """A and B each see only their own projects."""
    auth_client.post("/api/v1/projects/", json={})                         # A creates
    auth_client.post("/api/v1/projects/", json={}, headers=auth_client_b)  # B creates

    projects_a = auth_client.get("/api/v1/projects/").json()
    projects_b = auth_client.get("/api/v1/projects/", headers=auth_client_b).json()

    assert len(projects_a) == 1
    assert len(projects_b) == 1
    assert projects_a[0]["id"] != projects_b[0]["id"]


def test_download_isolated(auth_client, auth_client_b):
    """B cannot download A's project results — returns 404."""
    project_id = auth_client.post("/api/v1/projects/", json={}).json()["id"]

    r = auth_client.get(f"/api/v1/projects/{project_id}/download", headers=auth_client_b)
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────
# Task 12: output path uses tenant prefix
# ──────────────────────────────────────────────────────────────────

def test_output_path_contains_tenant_id(isolated_client_authed, test_db):
    """download endpoint reads from PROJECT_DIR/{tenant_id}/{project_id}/output/."""
    project = Project(
        id=str(uuid.uuid4()),
        status="completed",
        parameters={},
        tenant_id=FAKE_TENANT_ID,
    )
    test_db.add(project)
    test_db.commit()

    out_dir = PROJECT_DIR / FAKE_TENANT_ID / project.id / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "A_1_Arrets_Generiques.csv").write_text(
        "col_a;col_b\nval_1;val_2\n", encoding="utf-8-sig"
    )
    try:
        r = isolated_client_authed.get(f"/api/v1/projects/{project.id}/download")
        assert r.status_code == 200
        assert "application/zip" in r.headers["content-type"]
    finally:
        shutil.rmtree(PROJECT_DIR / FAKE_TENANT_ID / project.id, ignore_errors=True)
