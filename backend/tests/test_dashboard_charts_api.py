"""
test_dashboard_charts_api.py — Tests for the three dashboard-refonte endpoints.

Covers:
  - GET /{project_id}/charts/courses-by-jour-type
  - GET /{project_id}/charts/courses-by-hour  (jour_type + route_types filters)
  - GET /{project_id}/kpis                    (jour_type + route_types filters)
"""
import pytest
from sqlalchemy.orm import sessionmaker

import app.db.result_models  # noqa: F401 — registers all result models with Base
from app.db.models import Project
from app.db.result_models import (
    ResultA1ArretGenerique,
    ResultB1Ligne,
    ResultC1Course,
    ResultD2ServiceJourtype,
    ResultE1PassageAG,
    ResultF1CourseLigne,
    ResultF3KCCLigne,
)

PROJECT_ID = "proj-dashb"


@pytest.fixture(scope="module")
def dashboard_data(test_engine):
    """
    Seed two jour_types (1 and 2), two lines (bus route_type=3, tram=0),
    C_1 courses departing at 07:30, 08:45, 17:10 and 25:00 (next-day wrap),
    E_1 passages for 3 AGs.  The module-scoped fixture cleans up on teardown.
    """
    Session = sessionmaker(bind=test_engine)
    s = Session()

    s.add(Project(id=PROJECT_ID, status="completed", tenant_id="test-tenant-id"))

    # A_1 — 3 arrets
    s.add_all([
        ResultA1ArretGenerique(project_id=PROJECT_ID, id_ag_num=1, stop_name="AG1"),
        ResultA1ArretGenerique(project_id=PROJECT_ID, id_ag_num=2, stop_name="AG2"),
        ResultA1ArretGenerique(project_id=PROJECT_ID, id_ag_num=3, stop_name="AG3"),
    ])

    # B_1 — two lines: bus and tram
    s.add_all([
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=1, route_type=3, route_short_name="BUS1"),
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=2, route_type=0, route_short_name="TRAM1"),
    ])

    # D_2 — service 100 → jour 1, service 200 → jour 2
    s.add_all([
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=100, Type_Jour=1),
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=2, id_service_num=100, Type_Jour=1),
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=200, Type_Jour=2),
    ])

    # C_1 — one course per hour slot
    s.add_all([
        # Line 1 (bus), jour 1 — 3 courses at 07, 08, 17
        ResultC1Course(project_id=PROJECT_ID, id_course_num=10, id_ligne_num=1, id_service_num=100, heure_depart="07:30:00"),
        ResultC1Course(project_id=PROJECT_ID, id_course_num=11, id_ligne_num=1, id_service_num=100, heure_depart="08:45:00"),
        ResultC1Course(project_id=PROJECT_ID, id_course_num=12, id_ligne_num=1, id_service_num=100, heure_depart="17:10:00"),
        # Line 2 (tram), jour 1 — 1 course at 25:30 (next-day wrap → bucket 1)
        ResultC1Course(project_id=PROJECT_ID, id_course_num=20, id_ligne_num=2, id_service_num=100, heure_depart="25:30:00"),
        # Line 1 (bus), jour 2 — 1 course at 07
        ResultC1Course(project_id=PROJECT_ID, id_course_num=30, id_ligne_num=1, id_service_num=200, heure_depart="07:00:00"),
    ])

    # F_1 — aggregated per (ligne, jour_type)
    s.add_all([
        ResultF1CourseLigne(project_id=PROJECT_ID, id_ligne_num=1, type_jour=1, nb_course=3.0, route_short_name="BUS1"),
        ResultF1CourseLigne(project_id=PROJECT_ID, id_ligne_num=2, type_jour=1, nb_course=1.0, route_short_name="TRAM1"),
        ResultF1CourseLigne(project_id=PROJECT_ID, id_ligne_num=1, type_jour=2, nb_course=1.0, route_short_name="BUS1"),
    ])

    # F_3 — KCC per (ligne, jour_type)
    s.add_all([
        ResultF3KCCLigne(project_id=PROJECT_ID, id_ligne_num=1, type_jour=1, kcc=12.5),
        ResultF3KCCLigne(project_id=PROJECT_ID, id_ligne_num=2, type_jour=1, kcc=7.25),
        ResultF3KCCLigne(project_id=PROJECT_ID, id_ligne_num=1, type_jour=2, kcc=4.0),
    ])

    # E_1 — 3 AGs with passages on jour 1, 1 AG on jour 2
    s.add_all([
        ResultE1PassageAG(project_id=PROJECT_ID, id_ag_num=1, type_jour=1, nb_passage=10.0),
        ResultE1PassageAG(project_id=PROJECT_ID, id_ag_num=2, type_jour=1, nb_passage=5.0),
        ResultE1PassageAG(project_id=PROJECT_ID, id_ag_num=3, type_jour=1, nb_passage=3.0),
        ResultE1PassageAG(project_id=PROJECT_ID, id_ag_num=1, type_jour=2, nb_passage=1.0),
    ])

    s.commit()
    s.close()

    yield

    s = Session()
    for model in (
        ResultE1PassageAG, ResultF3KCCLigne, ResultF1CourseLigne, ResultC1Course,
        ResultD2ServiceJourtype, ResultB1Ligne, ResultA1ArretGenerique,
    ):
        s.query(model).filter(model.project_id == PROJECT_ID).delete(synchronize_session=False)
    s.query(Project).filter(Project.id == PROJECT_ID).delete(synchronize_session=False)
    s.commit()
    s.close()


# ── /charts/courses-by-jour-type ────────────────────────────────────────────

def test_courses_by_jour_type_aggregates(isolated_client_authed, dashboard_data):
    r = isolated_client_authed.get(f"/api/v1/projects/{PROJECT_ID}/charts/courses-by-jour-type")
    assert r.status_code == 200
    rows = r.json()["rows"]
    by_jt = {row["jour_type"]: row for row in rows}
    assert by_jt[1]["nb_courses"] == 4   # 3 (bus) + 1 (tram)
    assert by_jt[2]["nb_courses"] == 1
    # Labels should be populated from TYPE_JOUR_VAC_LABELS where available.
    assert "jour_type_name" in by_jt[1]


# ── /charts/courses-by-hour ─────────────────────────────────────────────────

def test_courses_by_hour_returns_24_buckets(isolated_client_authed, dashboard_data):
    r = isolated_client_authed.get(
        f"/api/v1/projects/{PROJECT_ID}/charts/courses-by-hour",
        params={"jour_type": 1},
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 24
    assert [row["heure"] for row in rows] == list(range(24))


def test_courses_by_hour_counts(isolated_client_authed, dashboard_data):
    r = isolated_client_authed.get(
        f"/api/v1/projects/{PROJECT_ID}/charts/courses-by-hour",
        params={"jour_type": 1},
    )
    buckets = {row["heure"]: row["nb_courses"] for row in r.json()["rows"]}
    # 07:30 → bucket 7, 08:45 → bucket 8, 17:10 → bucket 17, 25:30 → bucket 1
    assert buckets[7] == 1
    assert buckets[8] == 1
    assert buckets[17] == 1
    assert buckets[1] == 1
    # Empty buckets default to 0.
    assert buckets[2] == 0


def test_courses_by_hour_filters_route_types(isolated_client_authed, dashboard_data):
    """Only the tram line (route_type=0) should contribute."""
    r = isolated_client_authed.get(
        f"/api/v1/projects/{PROJECT_ID}/charts/courses-by-hour",
        params=[("jour_type", 1), ("route_types", "0")],
    )
    assert r.status_code == 200
    buckets = {row["heure"]: row["nb_courses"] for row in r.json()["rows"]}
    assert buckets[1] == 1
    assert buckets[7] == 0
    assert buckets[8] == 0
    assert buckets[17] == 0


def test_courses_by_hour_requires_jour_type(isolated_client_authed, dashboard_data):
    r = isolated_client_authed.get(f"/api/v1/projects/{PROJECT_ID}/charts/courses-by-hour")
    assert r.status_code == 422


# ── /kpis ───────────────────────────────────────────────────────────────────

def test_kpis_full(isolated_client_authed, dashboard_data):
    r = isolated_client_authed.get(
        f"/api/v1/projects/{PROJECT_ID}/kpis",
        params={"jour_type": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["nb_lignes"] == 2
    assert body["nb_arrets"] == 3
    assert body["nb_courses"] == 4
    assert body["kcc_total"] == pytest.approx(19.75)


def test_kpis_filtered_by_route_type(isolated_client_authed, dashboard_data):
    """Restricting to route_type=3 (bus) leaves 1 line, 3 courses, bus kcc only."""
    r = isolated_client_authed.get(
        f"/api/v1/projects/{PROJECT_ID}/kpis",
        params=[("jour_type", 1), ("route_types", "3")],
    )
    body = r.json()
    assert body["nb_lignes"] == 1
    assert body["nb_courses"] == 3
    assert body["kcc_total"] == pytest.approx(12.5)
    # nb_arrets stays project-wide per build_kpis docstring.
    assert body["nb_arrets"] == 3


def test_kpis_requires_jour_type(isolated_client_authed, dashboard_data):
    r = isolated_client_authed.get(f"/api/v1/projects/{PROJECT_ID}/kpis")
    assert r.status_code == 422
