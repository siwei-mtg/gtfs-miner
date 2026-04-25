"""
test_map_api.py — Tests for Task 30: GET /{project_id}/map/passage-ag

Fixtures: isolated_client_authed (function-scoped, in-memory DB, auth bypassed)
          map_data               (module-scoped, seeds/cleans up test rows)

Seed layout:
  - 1 Project (proj-t30, completed, tenant_id=test-tenant-id)
  - 2 E1 rows for AG 1 and AG 2, type_jour=1
  - 5 C2 rows with id_service_num:
      service 100 (Type_Jour=1): AG1-course 10 (ligne 1), AG1-course 11 (ligne 2),
                                 AG2-course 10 (ligne 1), AG2-course 12 (ligne 3)
      service 200 (Type_Jour=2): AG1-course 99 (ligne 1)   ← must NOT leak into jour_type=1
  - 3 B1 rows: ligne 1 → route_type=3 (bus), ligne 2 → route_type=0 (tram),
                         ligne 3 → route_type=3 (bus)
  - 2 D2 rows: (service 100 → Type_Jour=1), (service 200 → Type_Jour=2)

Expected for jour_type=1:
  AG1 by_route_type = {"3": 1, "0": 1}  → total 2  (course 99 filtered out)
  AG2 by_route_type = {"3": 2}          → total 2
"""
import pytest
from sqlalchemy.orm import sessionmaker

import app.db.result_models  # noqa: F401 — registers all result models with Base
from app.db.models import Project
from app.db.result_models import (
    ResultE1PassageAG,
    ResultC2Itineraire,
    ResultB1Ligne,
    ResultE4PassageArc,
    ResultA1ArretGenerique,
    ResultC3ItineraireArc,
    ResultD1ServiceDate,
    ResultD2ServiceJourtype,
)

# ── Constants ────────────────────────────────────────────────────────────────

PROJECT_ID = "proj-t30"
JOUR_TYPE = 1
BASE_URL = f"/api/v1/projects/{PROJECT_ID}/map/passage-ag"


# ── Seed fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def map_data(test_engine):
    """Seed project + E1/C2/B1 rows; clean up after module."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    # Project
    project = Project(
        id=PROJECT_ID,
        status="completed",
        tenant_id="test-tenant-id",
    )
    session.add(project)

    # E1: two AGs on jour_type=1; AG1 also has a jour_type=2 row to verify
    # the D2 filter via direct positive assertion at jour_type=2.
    # AG3 simulates a project with broken calendar (D2.Type_Jour NULL) — it
    # has a valid E_1 count but its service has no matching D2 Type_Jour row,
    # so the breakdown falls back to empty.
    session.add_all([
        ResultE1PassageAG(
            project_id=PROJECT_ID,
            id_ag_num=1,
            stop_name="Stop Alpha",
            stop_lat=48.85,
            stop_lon=2.35,
            type_jour=JOUR_TYPE,
            nb_passage=2.0,
        ),
        ResultE1PassageAG(
            project_id=PROJECT_ID,
            id_ag_num=2,
            stop_name="Stop Beta",
            stop_lat=48.86,
            stop_lon=2.36,
            type_jour=JOUR_TYPE,
            nb_passage=2.0,
        ),
        ResultE1PassageAG(
            project_id=PROJECT_ID,
            id_ag_num=1,
            stop_name="Stop Alpha",
            stop_lat=48.85,
            stop_lon=2.35,
            type_jour=2,
            nb_passage=1.0,
        ),
        ResultE1PassageAG(
            project_id=PROJECT_ID,
            id_ag_num=3,
            stop_name="Stop Gamma (broken D2)",
            stop_lat=48.87,
            stop_lon=2.37,
            type_jour=JOUR_TYPE,
            nb_passage=5.0,
        ),
    ])

    # B1: 3 lines
    session.add_all([
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=1, route_type=3),  # bus
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=2, route_type=0),  # tram
        ResultB1Ligne(project_id=PROJECT_ID, id_ligne_num=3, route_type=3),  # bus
    ])

    # C2: courses stopping at AGs, each carrying id_service_num.
    # Services 100 (Type_Jour=1) and 200 (Type_Jour=2) segregate operating days.
    # Course 99 (service 200) must be filtered out of jour_type=1 responses.
    # AG3's course 50 uses service 999 whose D2 row has Type_Jour=NULL —
    # this simulates the calendar-resolution gap seen in some older projects.
    session.add_all([
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=10, id_ligne_num=1, id_service_num=100),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=11, id_ligne_num=2, id_service_num=100),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=2, id_course_num=10, id_ligne_num=1, id_service_num=100),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=2, id_course_num=12, id_ligne_num=3, id_service_num=100),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=1, id_course_num=99, id_ligne_num=1, id_service_num=200),
        ResultC2Itineraire(project_id=PROJECT_ID, id_ag_num=3, id_course_num=50, id_ligne_num=1, id_service_num=999),
    ])

    # D2: service-to-Type_Jour mapping.  Each (id_ligne_num, id_service_num)
    # pair that appears in C2 needs a row here for the D2 JOIN to match.
    # Service 999 exists but Type_Jour is NULL to exercise the fallback path.
    session.add_all([
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=100, Type_Jour=1),
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=2, id_service_num=100, Type_Jour=1),
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=3, id_service_num=100, Type_Jour=1),
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=200, Type_Jour=2),
        ResultD2ServiceJourtype(project_id=PROJECT_ID, id_ligne_num=1, id_service_num=999, Type_Jour=None),
    ])

    session.commit()
    session.close()

    yield

    session = Session()
    session.query(ResultD2ServiceJourtype).filter(
        ResultD2ServiceJourtype.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(ResultC2Itineraire).filter(
        ResultC2Itineraire.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(ResultB1Ligne).filter(
        ResultB1Ligne.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(ResultE1PassageAG).filter(
        ResultE1PassageAG.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(Project).filter(
        Project.id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.commit()
    session.close()


# ── Tests ────────────────────────────────────────────────────────────────────

def test_passage_ag_structure(isolated_client_authed, map_data):
    """Response is a valid GeoJSON FeatureCollection; each feature has a
    Point geometry and properties containing by_route_type."""
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": JOUR_TYPE})
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    # 3 AGs seeded at jour_type=1: AG1, AG2, AG3 (AG3 simulates broken D2).
    assert len(body["features"]) == 3
    for feature in body["features"]:
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert len(feature["geometry"]["coordinates"]) == 2
        props = feature["properties"]
        assert "id_ag_num" in props
        assert "stop_name" in props
        assert "nb_passage_total" in props
        assert "by_route_type" in props
        assert isinstance(props["by_route_type"], dict)


def test_passage_ag_jour_type_required(isolated_client_authed, map_data):
    """Omitting jour_type query parameter returns HTTP 422."""
    r = isolated_client_authed.get(BASE_URL)
    assert r.status_code == 422


def test_passage_ag_total_authoritative_from_e1(isolated_client_authed, map_data):
    """nb_passage_total is read directly from E_1 (authoritative).
    The by_route_type breakdown is best-effort; when the D2 join covers all
    lines the sum matches the total, otherwise it is a lower bound.
    """
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": JOUR_TYPE})
    assert r.status_code == 200
    # E_1 seeds: AG1 nb_passage=2.0, AG2 nb_passage=2.0 at JOUR_TYPE=1.
    by_ag = {f["properties"]["id_ag_num"]: f["properties"] for f in r.json()["features"]}
    assert by_ag[1]["nb_passage_total"] == 2
    assert by_ag[2]["nb_passage_total"] == 2
    for feature in r.json()["features"]:
        props = feature["properties"]
        assert sum(props["by_route_type"].values()) <= props["nb_passage_total"]


def test_passage_ag_fallback_when_d2_type_jour_null(isolated_client_authed, map_data):
    """AG3's service has D2 row with Type_Jour=NULL, so the breakdown join
    returns nothing for it.  `nb_passage_total` must still render from E_1
    (5.0 → 5), proving the authoritative-E_1 fallback works and the frontend
    can show a neutral-color circle instead of an invisible marker."""
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": JOUR_TYPE})
    assert r.status_code == 200
    by_ag = {f["properties"]["id_ag_num"]: f["properties"] for f in r.json()["features"]}
    ag3 = by_ag[3]
    assert ag3["nb_passage_total"] == 5
    assert ag3["by_route_type"] == {}


def test_jour_types_returns_present_values(isolated_client_authed, map_data):
    """The /jour-types endpoint returns only jour_types that have E_1 rows,
    with labels from TYPE_JOUR_VAC_LABELS."""
    r = isolated_client_authed.get(f"/api/v1/projects/{PROJECT_ID}/map/jour-types")
    assert r.status_code == 200
    body = r.json()
    # Fixture seeds type_jour ∈ {1, 2} (AG1 has both, AG2 has only 1).
    values = [item["value"] for item in body]
    assert values == [1, 2]
    labels_by_value = {item["value"]: item["label"] for item in body}
    assert labels_by_value[1] == "Lundi_Scolaire"
    assert labels_by_value[2] == "Mardi_Scolaire"


def test_jour_types_missing_project_404(isolated_client_authed):
    """Unknown project_id → 404."""
    r = isolated_client_authed.get("/api/v1/projects/does-not-exist/map/jour-types")
    assert r.status_code == 404


def test_passage_ag_counts_respect_jour_type(isolated_client_authed, map_data):
    """Counts must be filtered by jour_type via D2.

    Regression guard: the fixture seeds course 99 on AG1 under service 200
    (Type_Jour=2). A query for jour_type=1 must NOT include it.
    Before the D2 join fix, AG1 totals incorrectly included course 99,
    inflating the bus count from 1 to 2.
    """
    r1 = isolated_client_authed.get(BASE_URL, params={"jour_type": 1})
    r2 = isolated_client_authed.get(BASE_URL, params={"jour_type": 2})
    assert r1.status_code == 200 and r2.status_code == 200

    by_ag_1 = {f["properties"]["id_ag_num"]: f["properties"] for f in r1.json()["features"]}
    by_ag_2 = {f["properties"]["id_ag_num"]: f["properties"] for f in r2.json()["features"]}

    # jour_type=1: only service-100 courses (10, 11, 12) count.
    assert by_ag_1[1]["by_route_type"] == {"3": 1, "0": 1}
    assert by_ag_1[1]["nb_passage_total"] == 2
    assert by_ag_1[2]["by_route_type"] == {"3": 2}
    assert by_ag_1[2]["nb_passage_total"] == 2

    # jour_type=2: only AG1 has an E1 row for day 2; only course 99 (bus) counts.
    assert 1 in by_ag_2 and 2 not in by_ag_2
    assert by_ag_2[1]["by_route_type"] == {"3": 1}
    assert by_ag_2[1]["nb_passage_total"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Task 31 — GET /{project_id}/map/passage-arc
# ═══════════════════════════════════════════════════════════════════════════════

"""
Seed layout (basic fixture — proj-t31):
  - 2 A1 rows: AG1(lat=48.85, lon=2.35), AG2(lat=48.88, lon=2.40)
  - 2 E4 rows: (a=1, b=2, nb=100, jour=1)  → direction="AB", weight=1.0
               (a=2, b=1, nb=40,  jour=1)  → direction="BA", weight=0.4

Seed layout (split fixture — proj-t31s):
  Same A1 + E4, plus:
  - B1: ligne 1 → route_type=3, ligne 2 → route_type=0
  - D1: service 10 → Type_Jour=1, service 11 → Type_Jour=1
  - C3: arc (1→2): course 10 via ligne 1 (service 10),
                   course 11 via ligne 2 (service 11)
    → route_type 3: 1 course, route_type 0: 1 course → fraction 0.5/0.5
"""

PROJECT_ID_ARC       = "proj-t31"
PROJECT_ID_ARC_SPLIT = "proj-t31s"
JOUR_TYPE_ARC        = 1
BASE_URL_ARC         = f"/api/v1/projects/{PROJECT_ID_ARC}/map/passage-arc"
BASE_URL_ARC_SPLIT   = f"/api/v1/projects/{PROJECT_ID_ARC_SPLIT}/map/passage-arc"


# ── Seed fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def arc_data(test_engine):
    """Seed Project + A1 + E4 rows for basic (no split_by) tests."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    session.add(Project(id=PROJECT_ID_ARC, status="completed", tenant_id="test-tenant-id"))

    session.add_all([
        ResultA1ArretGenerique(
            project_id=PROJECT_ID_ARC, id_ag_num=1,
            stop_name="Arc Stop A", stop_lat=48.85, stop_lon=2.35,
        ),
        ResultA1ArretGenerique(
            project_id=PROJECT_ID_ARC, id_ag_num=2,
            stop_name="Arc Stop B", stop_lat=48.88, stop_lon=2.40,
        ),
    ])
    session.add_all([
        ResultE4PassageArc(
            project_id=PROJECT_ID_ARC, id_ag_num_a=1, id_ag_num_b=2,
            nb_passage=100.0, type_jour=JOUR_TYPE_ARC,
        ),
        ResultE4PassageArc(
            project_id=PROJECT_ID_ARC, id_ag_num_a=2, id_ag_num_b=1,
            nb_passage=40.0, type_jour=JOUR_TYPE_ARC,
        ),
    ])
    session.commit()
    session.close()

    yield

    session = Session()
    session.query(ResultE4PassageArc).filter(
        ResultE4PassageArc.project_id == PROJECT_ID_ARC
    ).delete(synchronize_session=False)
    session.query(ResultA1ArretGenerique).filter(
        ResultA1ArretGenerique.project_id == PROJECT_ID_ARC
    ).delete(synchronize_session=False)
    session.query(Project).filter(
        Project.id == PROJECT_ID_ARC
    ).delete(synchronize_session=False)
    session.commit()
    session.close()


@pytest.fixture(scope="module")
def arc_split_data(test_engine):
    """Seed Project + A1 + E4 + B1 + D1 + C3 for split_by=route_type tests."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    session.add(Project(id=PROJECT_ID_ARC_SPLIT, status="completed", tenant_id="test-tenant-id"))

    session.add_all([
        ResultA1ArretGenerique(
            project_id=PROJECT_ID_ARC_SPLIT, id_ag_num=1,
            stop_name="Split Stop A", stop_lat=48.85, stop_lon=2.35,
        ),
        ResultA1ArretGenerique(
            project_id=PROJECT_ID_ARC_SPLIT, id_ag_num=2,
            stop_name="Split Stop B", stop_lat=48.88, stop_lon=2.40,
        ),
    ])
    session.add_all([
        ResultE4PassageArc(
            project_id=PROJECT_ID_ARC_SPLIT, id_ag_num_a=1, id_ag_num_b=2,
            nb_passage=100.0, type_jour=JOUR_TYPE_ARC,
        ),
        ResultE4PassageArc(
            project_id=PROJECT_ID_ARC_SPLIT, id_ag_num_a=2, id_ag_num_b=1,
            nb_passage=40.0, type_jour=JOUR_TYPE_ARC,
        ),
    ])
    session.add_all([
        ResultB1Ligne(project_id=PROJECT_ID_ARC_SPLIT, id_ligne_num=1, route_type=3),  # bus
        ResultB1Ligne(project_id=PROJECT_ID_ARC_SPLIT, id_ligne_num=2, route_type=0),  # tram
    ])
    session.add_all([
        ResultD1ServiceDate(
            project_id=PROJECT_ID_ARC_SPLIT, id_service_num=10, Type_Jour=JOUR_TYPE_ARC,
            service_id="svc10", Date_GTFS="20260101", Mois=1, Annee=2026,
        ),
        ResultD1ServiceDate(
            project_id=PROJECT_ID_ARC_SPLIT, id_service_num=11, Type_Jour=JOUR_TYPE_ARC,
            service_id="svc11", Date_GTFS="20260101", Mois=1, Annee=2026,
        ),
    ])
    # C3: arc (AG1→AG2): course 10 via ligne 1 (bus, service 10)
    #                    course 11 via ligne 2 (tram, service 11)
    session.add_all([
        ResultC3ItineraireArc(
            project_id=PROJECT_ID_ARC_SPLIT, id_course_num=10, id_ligne_num=1,
            id_service_num=10, id_ag_num_a=1, id_ag_num_b=2,
        ),
        ResultC3ItineraireArc(
            project_id=PROJECT_ID_ARC_SPLIT, id_course_num=11, id_ligne_num=2,
            id_service_num=11, id_ag_num_a=1, id_ag_num_b=2,
        ),
    ])
    session.commit()
    session.close()

    yield

    session = Session()
    session.query(ResultC3ItineraireArc).filter(
        ResultC3ItineraireArc.project_id == PROJECT_ID_ARC_SPLIT
    ).delete(synchronize_session=False)
    session.query(ResultD1ServiceDate).filter(
        ResultD1ServiceDate.project_id == PROJECT_ID_ARC_SPLIT
    ).delete(synchronize_session=False)
    session.query(ResultB1Ligne).filter(
        ResultB1Ligne.project_id == PROJECT_ID_ARC_SPLIT
    ).delete(synchronize_session=False)
    session.query(ResultE4PassageArc).filter(
        ResultE4PassageArc.project_id == PROJECT_ID_ARC_SPLIT
    ).delete(synchronize_session=False)
    session.query(ResultA1ArretGenerique).filter(
        ResultA1ArretGenerique.project_id == PROJECT_ID_ARC_SPLIT
    ).delete(synchronize_session=False)
    session.query(Project).filter(
        Project.id == PROJECT_ID_ARC_SPLIT
    ).delete(synchronize_session=False)
    session.commit()
    session.close()


# ── Basic tests (split_by="none") ─────────────────────────────────────────────

def test_passage_arc_has_direction(isolated_client_authed, arc_data):
    """Every feature has a direction property with value 'AB' or 'BA'."""
    r = isolated_client_authed.get(BASE_URL_ARC, params={"jour_type": JOUR_TYPE_ARC})
    assert r.status_code == 200
    for feature in r.json()["features"]:
        assert feature["properties"]["direction"] in ("AB", "BA")


def test_passage_arc_ab_ba_separate(isolated_client_authed, arc_data):
    """Both 'AB' and 'BA' direction features exist for the seeded pair."""
    r = isolated_client_authed.get(BASE_URL_ARC, params={"jour_type": JOUR_TYPE_ARC})
    assert r.status_code == 200
    directions = {f["properties"]["direction"] for f in r.json()["features"]}
    assert "AB" in directions
    assert "BA" in directions


def test_passage_arc_geometry_is_linestring(isolated_client_authed, arc_data):
    """Each feature geometry is a LineString with exactly 2 coordinate pairs."""
    r = isolated_client_authed.get(BASE_URL_ARC, params={"jour_type": JOUR_TYPE_ARC})
    assert r.status_code == 200
    for feature in r.json()["features"]:
        geom = feature["geometry"]
        assert geom["type"] == "LineString"
        assert len(geom["coordinates"]) == 2


def test_passage_arc_geometry_orientation_normalized(isolated_client_authed, arc_data):
    """AB and BA features for the same AG pair share the same LineString
    orientation (lower→higher AG id), so renderer offset expressions with
    `sign(direction)` can place them on opposite sides of the centerline."""
    r = isolated_client_authed.get(BASE_URL_ARC, params={"jour_type": JOUR_TYPE_ARC})
    assert r.status_code == 200
    # Group coordinates by the unordered AG pair; all features sharing a pair
    # must have identical coordinates (same orientation).
    by_pair: dict[tuple[int, int], set[tuple]] = {}
    for f in r.json()["features"]:
        a = f["properties"]["id_ag_num_a"]
        b = f["properties"]["id_ag_num_b"]
        key = tuple(sorted((a, b)))
        by_pair.setdefault(key, set()).add(
            tuple(tuple(c) for c in f["geometry"]["coordinates"])
        )
    for key, coord_sets in by_pair.items():
        assert len(coord_sets) == 1, (
            f"AB and BA geometries diverge for pair {key}: {coord_sets}"
        )


def test_passage_arc_weight_normalized(isolated_client_authed, arc_data):
    """max(weight) == 1.0 and all weights are in [0.0, 1.0]."""
    r = isolated_client_authed.get(BASE_URL_ARC, params={"jour_type": JOUR_TYPE_ARC})
    assert r.status_code == 200
    weights = [f["properties"]["weight"] for f in r.json()["features"]]
    assert max(weights) == pytest.approx(1.0)
    assert all(0.0 <= w <= 1.0 for w in weights)


def test_passage_arc_jour_type_required(isolated_client_authed, arc_data):
    """Omitting jour_type returns HTTP 422."""
    r = isolated_client_authed.get(BASE_URL_ARC)
    assert r.status_code == 422


# ── Split tests (split_by="route_type") ───────────────────────────────────────

def test_passage_arc_split_returns_multiple_features_per_arc(
    isolated_client_authed, arc_split_data
):
    """With 2 route_types on arc (1→2), that arc returns 2 features."""
    r = isolated_client_authed.get(
        BASE_URL_ARC_SPLIT,
        params={"jour_type": JOUR_TYPE_ARC, "split_by": "route_type"},
    )
    assert r.status_code == 200
    # Count features for arc (a=1, b=2) direction AB
    ab_features = [
        f for f in r.json()["features"]
        if f["properties"]["id_ag_num_a"] == 1
        and f["properties"]["id_ag_num_b"] == 2
        and f["properties"]["direction"] == "AB"
    ]
    assert len(ab_features) == 2, "Expected one feature per route_type for arc AB (1→2)"


def test_passage_arc_split_fractions_sum_to_one(isolated_client_authed, arc_split_data):
    """fraction_of_direction values for the same arc+direction sum to 1.0."""
    r = isolated_client_authed.get(
        BASE_URL_ARC_SPLIT,
        params={"jour_type": JOUR_TYPE_ARC, "split_by": "route_type"},
    )
    assert r.status_code == 200
    ab_features = [
        f for f in r.json()["features"]
        if f["properties"]["id_ag_num_a"] == 1
        and f["properties"]["id_ag_num_b"] == 2
        and f["properties"]["direction"] == "AB"
    ]
    total_fraction = sum(f["properties"]["fraction_of_direction"] for f in ab_features)
    assert total_fraction == pytest.approx(1.0, abs=1e-5)


def test_passage_arc_split_cumulative_start_ordered(isolated_client_authed, arc_split_data):
    """cumulative_fraction_start values are non-decreasing (stacking order preserved)."""
    r = isolated_client_authed.get(
        BASE_URL_ARC_SPLIT,
        params={"jour_type": JOUR_TYPE_ARC, "split_by": "route_type"},
    )
    assert r.status_code == 200
    ab_features = sorted(
        [
            f for f in r.json()["features"]
            if f["properties"]["id_ag_num_a"] == 1
            and f["properties"]["id_ag_num_b"] == 2
            and f["properties"]["direction"] == "AB"
        ],
        key=lambda f: f["properties"]["cumulative_fraction_start"],
    )
    assert len(ab_features) >= 2
    starts = [f["properties"]["cumulative_fraction_start"] for f in ab_features]
    assert starts == sorted(starts), "cumulative_fraction_start must be non-decreasing"
    # First sub-rect must start at 0 (immediately adjacent to centerline gap)
    assert starts[0] == pytest.approx(0.0)
