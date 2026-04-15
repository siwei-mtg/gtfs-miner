"""
test_geopackage_export.py — Tests for Task 32:
    GET /{project_id}/export/geopackage

Seed layout (gpkg_data fixture — proj-t32):
  - 2 A1 rows: AG1(lat=48.85, lon=2.35), AG2(lat=48.88, lon=2.40)
  - 2 A2 rows: AP1(lat=48.85, lon=2.35), AP2(lat=48.86, lon=2.37)
  - 2 E1 rows: AG1 nb_passage=5.0, AG2 nb_passage=3.0, type_jour=1
  - 2 E4 rows: (a=1,b=2,nb=100,jour=1) → AB; (a=2,b=1,nb=40,jour=1) → BA

Expected GeoPackage layers: passage_ag, passage_arc,
                             arrets_generiques, arrets_physiques
"""
import io
import tempfile
from pathlib import Path

import fiona
import pytest
from sqlalchemy.orm import sessionmaker

import app.db.result_models  # noqa: F401 — registers all result models with Base
from app.db.models import Project
from app.db.result_models import (
    ResultA1ArretGenerique,
    ResultA2ArretPhysique,
    ResultE1PassageAG,
    ResultE4PassageArc,
)

# ── Constants ─────────────────────────────────────────────────────────────────

PROJECT_ID = "proj-t32"
JOUR_TYPE  = 1
BASE_URL   = f"/api/v1/projects/{PROJECT_ID}/export/geopackage"

EXPECTED_LAYERS = {"passage_ag", "passage_arc", "arrets_generiques", "arrets_physiques"}


# ── Seed fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def gpkg_data(test_engine):
    """Seed Project + A1 + A2 + E1 + E4 rows; clean up after module."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    session.add(Project(id=PROJECT_ID, status="completed", tenant_id="test-tenant-id"))

    session.add_all([
        ResultA1ArretGenerique(
            project_id=PROJECT_ID, id_ag_num=1, id_ag="AG001",
            stop_name="Stop A", stop_lat=48.85, stop_lon=2.35,
        ),
        ResultA1ArretGenerique(
            project_id=PROJECT_ID, id_ag_num=2, id_ag="AG002",
            stop_name="Stop B", stop_lat=48.88, stop_lon=2.40,
        ),
    ])
    session.add_all([
        ResultA2ArretPhysique(
            project_id=PROJECT_ID, id_ap_num=1, id_ap="AP001",
            id_ag="AG001", id_ag_num=1,
            stop_name="Phys A", stop_lat=48.85, stop_lon=2.35,
        ),
        ResultA2ArretPhysique(
            project_id=PROJECT_ID, id_ap_num=2, id_ap="AP002",
            id_ag="AG002", id_ag_num=2,
            stop_name="Phys B", stop_lat=48.86, stop_lon=2.37,
        ),
    ])
    session.add_all([
        ResultE1PassageAG(
            project_id=PROJECT_ID, id_ag_num=1,
            stop_name="Stop A", stop_lat=48.85, stop_lon=2.35,
            type_jour=JOUR_TYPE, nb_passage=5.0,
        ),
        ResultE1PassageAG(
            project_id=PROJECT_ID, id_ag_num=2,
            stop_name="Stop B", stop_lat=48.88, stop_lon=2.40,
            type_jour=JOUR_TYPE, nb_passage=3.0,
        ),
    ])
    session.add_all([
        ResultE4PassageArc(
            project_id=PROJECT_ID, id_ag_num_a=1, id_ag_num_b=2,
            nb_passage=100.0, type_jour=JOUR_TYPE,
        ),
        ResultE4PassageArc(
            project_id=PROJECT_ID, id_ag_num_a=2, id_ag_num_b=1,
            nb_passage=40.0,  type_jour=JOUR_TYPE,
        ),
    ])
    session.commit()
    session.close()

    yield

    session = Session()
    session.query(ResultE4PassageArc).filter(
        ResultE4PassageArc.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(ResultE1PassageAG).filter(
        ResultE1PassageAG.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(ResultA2ArretPhysique).filter(
        ResultA2ArretPhysique.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(ResultA1ArretGenerique).filter(
        ResultA1ArretGenerique.project_id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.query(Project).filter(
        Project.id == PROJECT_ID
    ).delete(synchronize_session=False)
    session.commit()
    session.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def _save_gpkg(client, url, params) -> Path:
    """Call the endpoint and save the response bytes to a temp .gpkg file."""
    r = client.get(url, params=params)
    assert r.status_code == 200
    tmp = Path(tempfile.mktemp(suffix=".gpkg"))
    tmp.write_bytes(r.content)
    return tmp


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_gpkg_file_created(isolated_client_authed, gpkg_data):
    """Endpoint returns 200 with application/geopackage+sqlite3 content-type."""
    r = isolated_client_authed.get(BASE_URL, params={"jour_type": JOUR_TYPE})
    assert r.status_code == 200
    assert "geopackage" in r.headers["content-type"]
    assert len(r.content) > 0


def test_gpkg_contains_expected_layers(isolated_client_authed, gpkg_data):
    """GeoPackage contains all four expected layer names."""
    tmp = _save_gpkg(isolated_client_authed, BASE_URL, {"jour_type": JOUR_TYPE})
    try:
        layers = set(fiona.listlayers(str(tmp)))
        assert EXPECTED_LAYERS == layers, (
            f"Expected layers {EXPECTED_LAYERS}, got {layers}"
        )
    finally:
        tmp.unlink(missing_ok=True)


def test_gpkg_passage_ag_has_nb_passage(isolated_client_authed, gpkg_data):
    """passage_ag layer contains an nb_passage field with values > 0."""
    tmp = _save_gpkg(isolated_client_authed, BASE_URL, {"jour_type": JOUR_TYPE})
    try:
        with fiona.open(str(tmp), layer="passage_ag") as src:
            assert "nb_passage" in src.schema["properties"]
            values = [f["properties"]["nb_passage"] for f in src]
            assert len(values) > 0
            assert all(v > 0 for v in values)
    finally:
        tmp.unlink(missing_ok=True)


def test_gpkg_arc_single_layer_with_direction(isolated_client_authed, gpkg_data):
    """passage_arc is a single layer containing both AB and BA rows."""
    tmp = _save_gpkg(isolated_client_authed, BASE_URL, {"jour_type": JOUR_TYPE})
    try:
        with fiona.open(str(tmp), layer="passage_arc") as src:
            assert "direction" in src.schema["properties"]
            directions = {f["properties"]["direction"] for f in src}
            assert "AB" in directions, "Expected AB direction in passage_arc"
            assert "BA" in directions, "Expected BA direction in passage_arc"
    finally:
        tmp.unlink(missing_ok=True)


def test_gpkg_batch_no_duplicate_features(isolated_client_authed, gpkg_data):
    """passage_arc row count equals the number of seeded E4 rows (no duplicates)."""
    tmp = _save_gpkg(isolated_client_authed, BASE_URL, {"jour_type": JOUR_TYPE})
    try:
        with fiona.open(str(tmp), layer="passage_arc") as src:
            count = len(list(src))
        # 2 E4 rows seeded → 2 passage_arc features
        assert count == 2, f"Expected 2 passage_arc features, got {count}"
    finally:
        tmp.unlink(missing_ok=True)


def test_gpkg_arc_geometry_is_linestring(isolated_client_authed, gpkg_data):
    """passage_arc features use LineString geometry (not Polygon)."""
    tmp = _save_gpkg(isolated_client_authed, BASE_URL, {"jour_type": JOUR_TYPE})
    try:
        with fiona.open(str(tmp), layer="passage_arc") as src:
            geom_types = {f["geometry"]["type"] for f in src}
        assert geom_types == {"LineString"}, f"Expected LineString, got {geom_types}"
    finally:
        tmp.unlink(missing_ok=True)


def test_gpkg_arc_has_max_nb_passage(isolated_client_authed, gpkg_data):
    """passage_arc has max_nb_passage field equal to the layer-wide maximum."""
    tmp = _save_gpkg(isolated_client_authed, BASE_URL, {"jour_type": JOUR_TYPE})
    try:
        with fiona.open(str(tmp), layer="passage_arc") as src:
            assert "max_nb_passage" in src.schema["properties"]
            values = [f["properties"]["max_nb_passage"] for f in src]
        # Seeded: nb_passage=100 and 40 → max=100
        assert all(v == 100.0 for v in values), f"Expected max=100.0, got {values}"
    finally:
        tmp.unlink(missing_ok=True)
