"""
test_charts_api.py — Tests for Task 37A: GET /{project_id}/charts/peak-offpeak.

Seed layout (project proj-t37):
  - 1 Project (completed, tenant_id=test-tenant-id)
  - A_1:  AG 1 "Stop Alpha", AG 2 "Stop Beta"
  - B_1:  id_ligne_num=1 (bus)
  - D_2:  (id_ligne_num=1, id_service_num=100) → Type_Jour=1
          (id_ligne_num=1, id_service_num=200) → Type_Jour=2
  - C_2:  (service 100)
            AG 1 course 10 heure_depart="07:30:00"  → peak HPM
            AG 1 course 11 heure_depart="12:00:00"  → off-peak HC
            AG 1 course 12 heure_depart="17:45:00"  → peak HPS
            AG 2 course 10 heure_depart="07:30:00"  → peak HPM
            AG 2 course 12 heure_depart="17:45:00"  → peak HPS
          (service 200, must NOT leak into jour_type=1)
            AG 1 course 99 heure_depart="08:00:00"  → peak HPM
  - E_1:  AG 1 type_jour=1 nb_passage=3  (equals invariant)
          AG 2 type_jour=1 nb_passage=2

Expected for jour_type=1:
  AG 1 peak=2 (courses 10+12), offpeak=1 (course 11)  → total 3
  AG 2 peak=2 (courses 10+12), offpeak=0              → total 2
"""
import pytest
from sqlalchemy.orm import sessionmaker

import app.db.result_models  # noqa: F401 — registers all result models with Base
from app.db.models import Project
from app.db.result_models import (
    ResultA1ArretGenerique,
    ResultB1Ligne,
    ResultC2Itineraire,
    ResultD2ServiceJourtype,
    ResultE1PassageAG,
)

# ── Constants ────────────────────────────────────────────────────────────────

PROJECT_ID = "proj-t37"
JOUR_TYPE = 1
BASE_URL = f"/api/v1/projects/{PROJECT_ID}/charts/peak-offpeak"


# ── Seed fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def chart_data(test_engine):
    """Seed project + A1 + B1 + C2 + D2 + E1 rows; clean up after module."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    session.add(Project(
        id=PROJECT_ID,
        status="completed",
        tenant_id="test-tenant-id",
    ))

    session.add_all([
        ResultA1ArretGenerique(project_id=PROJECT_ID, id_ag_num=1, stop_name="Stop Alpha"),
        ResultA1ArretGenerique(project_id=PROJECT_ID, id_ag_num=2, stop_name="Stop Beta"),
    ])

    session.add_all([
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=1, route_type=3),
    ])

    session.add_all([
        # Service 100 → Type_Jour=1 (the jour we probe)
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=100, Type_Jour=1),
        # Service 200 → Type_Jour=2 (must be filtered out for jour_type=1)
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=200, Type_Jour=2),
    ])

    session.add_all([
        # AG 1 under service 100: peak / off-peak / peak
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=10, id_ligne_num=1, id_service_num=100, heure_depart="07:30:00"),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=11, id_ligne_num=1, id_service_num=100, heure_depart="12:00:00"),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=12, id_ligne_num=1, id_service_num=100, heure_depart="17:45:00"),
        # AG 2 under service 100: peak / peak
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=2, id_course_num=10, id_ligne_num=1, id_service_num=100, heure_depart="07:30:00"),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=2, id_course_num=12, id_ligne_num=1, id_service_num=100, heure_depart="17:45:00"),
        # Service 200 → Type_Jour=2 → must NOT appear in jour_type=1 results.
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=99, id_ligne_num=1, id_service_num=200, heure_depart="08:00:00"),
    ])

    session.add_all([
        ResultE1PassageAG(project_id=PROJECT_ID, id_ag_num=1, stop_name="Stop Alpha",
                          stop_lat=48.85, stop_lon=2.35, type_jour=JOUR_TYPE, nb_passage=3.0),
        ResultE1PassageAG(project_id=PROJECT_ID, id_ag_num=2, stop_name="Stop Beta",
                          stop_lat=48.86, stop_lon=2.36, type_jour=JOUR_TYPE, nb_passage=2.0),
    ])

    session.commit()
    session.close()

    yield

    session = Session()
    for model in (
        ResultE1PassageAG, ResultC2Itineraire, ResultD2ServiceJourtype,
        ResultB1Ligne, ResultA1ArretGenerique,
    ):
        session.query(model).filter(model.project_id == PROJECT_ID).delete(synchronize_session=False)
    session.query(Project).filter(Project.id == PROJECT_ID).delete(synchronize_session=False)
    session.commit()
    session.close()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_peak_offpeak_returns_rows(isolated_client_authed, chart_data):
    """Response shape: {"rows": [{id_ag_num, stop_name, peak_count, offpeak_count}]}."""
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": JOUR_TYPE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body
    required = {"id_ag_num", "stop_name", "peak_count", "offpeak_count"}
    assert all(required <= row.keys() for row in body["rows"])
    assert len(body["rows"]) == 2


def test_peak_offpeak_counts_sum_matches_e1(isolated_client_authed, chart_data):
    """peak + offpeak per AG equals E_1.nb_passage when D2 is fully resolved."""
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": JOUR_TYPE})
    by_ag = {row["id_ag_num"]: row for row in r.json()["rows"]}

    assert by_ag[1]["peak_count"] == 2
    assert by_ag[1]["offpeak_count"] == 1
    assert by_ag[1]["peak_count"] + by_ag[1]["offpeak_count"] == 3  # E_1 AG1 nb_passage

    assert by_ag[2]["peak_count"] == 2
    assert by_ag[2]["offpeak_count"] == 0
    assert by_ag[2]["peak_count"] + by_ag[2]["offpeak_count"] == 2  # E_1 AG2 nb_passage


def test_peak_offpeak_jour_type_required(isolated_client_authed, chart_data):
    """Omitting jour_type returns 422 (FastAPI query-param validation)."""
    r = isolated_client_authed.get(BASE_URL)
    assert r.status_code == 422


def test_peak_offpeak_filters_by_jour_type(isolated_client_authed, chart_data):
    """jour_type=2 returns only service-200 rows → AG 1 peak=1, offpeak=0, AG 2 absent."""
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": 2})
    assert r.status_code == 200
    rows = r.json()["rows"]
    by_ag = {row["id_ag_num"]: row for row in rows}
    assert 2 not in by_ag  # AG 2 has no service-200 C_2 rows
    assert by_ag[1]["peak_count"] == 1  # course 99 at 08:00 is peak
    assert by_ag[1]["offpeak_count"] == 0
