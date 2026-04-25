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
from app.db.result_models import (
    ResultA1ArretGenerique,
    ResultB1Ligne,
    ResultF1CourseLigne,
)

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

    # B_1 rows for Task 38A enum-filter tests.  route_type values: 3, 3, 0
    # so filter_values="3" returns 2 rows, filter_values="3,0" returns 3 rows.
    session.add_all([
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=1, route_short_name="L1", route_type=3),
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=2, route_short_name="L2", route_type=3),
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=3, route_short_name="T3", route_type=0),
    ])

    # F_1 rows for Task 38A range-filter tests.
    # nb_course values: 10, 25, 50, 80, 150 (single type_jour=1 for simplicity).
    session.add_all([
        ResultF1CourseLigne(project_id=PROJECT_ID, id_ligne_num=i, route_short_name=f"L{i}",
                             type_jour=1, nb_course=v)
        for i, v in enumerate([10.0, 25.0, 50.0, 80.0, 150.0], start=1)
    ])

    session.commit()
    session.close()

    yield

    session = Session()
    for model in (ResultF1CourseLigne, ResultB1Ligne, ResultA1ArretGenerique):
        session.query(model).filter(model.project_id == PROJECT_ID).delete(synchronize_session=False)
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


# ── Task 20: single-table CSV download ──────────────────────────────────────

DOWNLOAD_URL = f"/api/v1/projects/{PROJECT_ID}/tables/a1/download"


def test_single_table_csv_download(isolated_client_authed, result_data):
    r = isolated_client_authed.get(DOWNLOAD_URL)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    # UTF-8 BOM: first 3 bytes must be EF BB BF
    assert r.content[:3] == b"\xef\xbb\xbf"
    # semicolon-delimited: header line contains ";"
    first_line = r.content.decode("utf-8-sig").splitlines()[0]
    assert ";" in first_line


def test_single_table_csv_columns(isolated_client_authed, result_data):
    r = isolated_client_authed.get(DOWNLOAD_URL)
    assert r.status_code == 200
    first_line = r.content.decode("utf-8-sig").splitlines()[0]
    csv_cols = first_line.split(";")
    # internal fields must not appear
    assert "id" not in csv_cols
    assert "project_id" not in csv_cols
    # domain columns must be present
    for col in ("id_ag", "stop_name", "stop_lat", "stop_lon", "id_ag_num"):
        assert col in csv_cols


# ── Task 38A: enum multi-select + numeric range filters ─────────────────────

def test_filter_values_single_value(isolated_client_authed, result_data):
    """filter_field=route_type&filter_values=3 returns only the matching rows."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=route_type&filter_values=3"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    assert all(row["route_type"] == 3 for row in rows)


def test_filter_values_csv_list(isolated_client_authed, result_data):
    """filter_values accepts a comma-separated list — SQL IN (...) semantics."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=route_type&filter_values=3,0"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 3
    assert all(row["route_type"] in (3, 0) for row in rows)


def test_range_filter(isolated_client_authed, result_data):
    """range_min / range_max clip rows to [min, max] inclusive."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/f1?range_field=nb_course&range_min=20&range_max=100"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    # Fixture values 10, 25, 50, 80, 150 → inside [20, 100] = 25, 50, 80
    assert {row["nb_course"] for row in rows} == {25.0, 50.0, 80.0}


def test_range_filter_min_only(isolated_client_authed, result_data):
    """Supplying only range_min applies a lower bound without an upper bound."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/f1?range_field=nb_course&range_min=50"
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert {row["nb_course"] for row in rows} == {50.0, 80.0, 150.0}


def test_invalid_filter_field_returns_400(isolated_client_authed, result_data):
    """Requesting filter_field=<unknown column> must error out with 400."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=nonexistent&filter_values=x"
    )
    assert r.status_code == 400


def test_invalid_range_field_returns_400(isolated_client_authed, result_data):
    """Requesting range_field=<unknown column> must error out with 400."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/f1?range_field=nonexistent&range_min=0"
    )
    assert r.status_code == 400


def test_internal_field_not_filterable(isolated_client_authed, result_data):
    """project_id / id must never be filterable via the public API (tenant leak)."""
    r = isolated_client_authed.get(
        f"{BASE_URL}/b1?filter_field=project_id&filter_values={PROJECT_ID}"
    )
    assert r.status_code == 400
