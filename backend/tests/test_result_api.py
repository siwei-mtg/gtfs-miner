"""
test_result_api.py — Tests for Task 19: GET /{project_id}/tables/{table_name}

Fixtures: isolated_client_authed (function-scoped, in-memory DB, auth bypassed)
          result_data           (module-scoped, seeds/cleans up test rows)

The fake_user injected by isolated_client_authed has tenant_id="test-tenant-id".
"""
import pytest
from sqlalchemy.orm import sessionmaker

import app.db.result_models  # noqa: F401 — registers result table models with Base
from app.db.models import Project
from app.db.result_models import ResultA1ArretGenerique

# ── Test constants ──────────────────────────────────────────────────────────
PROJECT_ID = "proj-t19"
OTHER_PROJECT_ID = "proj-t19-other"
BASE_URL = f"/api/v1/projects/{PROJECT_ID}/tables"


# ── Module-scoped seed fixture ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def result_data(test_engine):
    """Seed test project + 5 ResultA1 rows; clean up after module."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    project = Project(id=PROJECT_ID, status="completed", tenant_id="test-tenant-id")
    other_project = Project(id=OTHER_PROJECT_ID, status="completed", tenant_id="other-tenant-id")
    session.add_all([project, other_project])

    rows = [
        ResultA1ArretGenerique(
            project_id=PROJECT_ID,
            id_ag=f"AG00{i}",
            stop_name=f"Stop {chr(64 + i)}",  # Stop A … Stop E
            stop_lat=48.80 + i * 0.01,
            stop_lon=2.30 + i * 0.01,
            id_ag_num=i,
        )
        for i in range(1, 6)
    ]
    session.add_all(rows)
    session.commit()
    session.close()

    yield

    session = Session()
    session.query(ResultA1ArretGenerique).filter(
        ResultA1ArretGenerique.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(Project).filter(
        Project.id.in_([PROJECT_ID, OTHER_PROJECT_ID])
    ).delete(synchronize_session=False)
    session.commit()
    session.close()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_get_table_a1_paginated(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["rows"]) == 5
    assert "id" not in body["columns"]
    assert "project_id" not in body["columns"]
    assert "stop_name" in body["columns"]
    for row in body["rows"]:
        assert "id" not in row
        assert "project_id" not in row


def test_get_table_unknown(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/zzz")
    assert r.status_code == 404


def test_get_table_wrong_project(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"/api/v1/projects/{OTHER_PROJECT_ID}/tables/a1")
    assert r.status_code == 404


def test_sort_by_column(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1?sort_by=stop_name&sort_order=desc")
    assert r.status_code == 200
    names = [row["stop_name"] for row in r.json()["rows"]]
    assert names == sorted(names, reverse=True)


def test_text_search(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1?q=Stop+A")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) >= 1
    for row in rows:
        assert "Stop A" in row["stop_name"]


def test_limit_max_200(isolated_client_authed, result_data):
    r = isolated_client_authed.get(f"{BASE_URL}/a1?limit=500")
    assert r.status_code == 200
    assert len(r.json()["rows"]) <= 200


def test_total_count_correct(isolated_client_authed, result_data, test_db):
    r = isolated_client_authed.get(f"{BASE_URL}/a1")
    assert r.status_code == 200
    expected = test_db.query(ResultA1ArretGenerique).filter(
        ResultA1ArretGenerique.project_id == PROJECT_ID
    ).count()
    assert r.json()["total"] == expected
