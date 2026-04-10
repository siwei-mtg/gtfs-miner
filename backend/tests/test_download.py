"""
test_download.py — Task 3 (happy-path) + Task 4 (error-cases) for download endpoint.

Design: no pipeline execution — dummy CSVs are written directly to the output
directory, making all tests sub-second.

Fixtures used:
  isolated_client_authed — TestClient with in-memory DB (get_db overridden)
  test_db         — SQLAlchemy session on the same in-memory engine
Both share test_engine so committed rows are immediately visible across sessions.
"""
import io
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest

from app.db.models import Project
from app.core.config import PROJECT_DIR
from .conftest import EXPECTED_CSVS

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _make_project(test_db, status: str = "completed") -> str:
    """Insert a project row with the given status; return its ID."""
    project_id = str(uuid.uuid4())
    project = Project(id=project_id, status=status, parameters={})
    test_db.add(project)
    test_db.commit()
    return project_id


def _create_output_csvs(project_id: str) -> Path:
    """Create all 15 dummy CSV files in the project output dir."""
    out_dir = PROJECT_DIR / project_id / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in EXPECTED_CSVS:
        (out_dir / name).write_text("col_a;col_b\nval_1;val_2\n", encoding="utf-8-sig")
    return out_dir


def _cleanup(project_id: str) -> None:
    project_dir = PROJECT_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)


# ──────────────────────────────────────────────────────────────────
# Task 3: happy-path
# ──────────────────────────────────────────────────────────────────

def test_download_completed_project(isolated_client_authed, test_db):
    """HTTP 200, content-type zip, ZIP contains all 15 non-empty CSVs."""
    project_id = _make_project(test_db, status="completed")
    _create_output_csvs(project_id)
    try:
        resp = isolated_client_authed.get(f"/api/v1/projects/{project_id}/download")
        assert resp.status_code == 200
        assert "application/zip" in resp.headers["content-type"]

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            assert sorted(names) == sorted(EXPECTED_CSVS), \
                f"Expected {sorted(EXPECTED_CSVS)}, got {sorted(names)}"
            for name in names:
                assert len(zf.read(name)) > 0, f"{name} is empty in ZIP"
    finally:
        _cleanup(project_id)


def test_download_filename(isolated_client_authed, test_db):
    """Content-Disposition contains the correct filename."""
    project_id = _make_project(test_db, status="completed")
    _create_output_csvs(project_id)
    try:
        resp = isolated_client_authed.get(f"/api/v1/projects/{project_id}/download")
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert f'filename="gtfs_results_{project_id}.zip"' in cd
    finally:
        _cleanup(project_id)


# ──────────────────────────────────────────────────────────────────
# Task 4: error-cases
# ──────────────────────────────────────────────────────────────────

def test_download_nonexistent_project(isolated_client_authed):
    """Random UUID → 404."""
    resp = isolated_client_authed.get(f"/api/v1/projects/{uuid.uuid4()}/download")
    assert resp.status_code == 404


def test_download_pending_project(isolated_client_authed, test_db):
    """status=pending → 400."""
    project_id = _make_project(test_db, status="pending")
    resp = isolated_client_authed.get(f"/api/v1/projects/{project_id}/download")
    assert resp.status_code == 400


def test_download_processing_project(isolated_client_authed, test_db):
    """status=processing → 400."""
    project_id = _make_project(test_db, status="processing")
    resp = isolated_client_authed.get(f"/api/v1/projects/{project_id}/download")
    assert resp.status_code == 400


def test_download_failed_project(isolated_client_authed, test_db):
    """status=failed → 400."""
    project_id = _make_project(test_db, status="failed")
    resp = isolated_client_authed.get(f"/api/v1/projects/{project_id}/download")
    assert resp.status_code == 400


def test_download_no_output_dir(isolated_client_authed, test_db):
    """status=completed but output dir absent → 404."""
    project_id = _make_project(test_db, status="completed")
    # Intentionally no _create_output_csvs call
    resp = isolated_client_authed.get(f"/api/v1/projects/{project_id}/download")
    assert resp.status_code == 404
