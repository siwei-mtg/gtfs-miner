"""
test_worker_celery.py — GROUP D: Celery task unit tests (Task 14).

No Redis required — uses task_always_eager to execute tasks synchronously.
"""
import shutil
from pathlib import Path

import pytest

from app.celery_app import celery


def test_task_registered():
    """gtfs_miner.process_project must be present in Celery's task registry."""
    import app.services.worker  # trigger @celery.task registration  # noqa: F401
    assert "gtfs_miner.process_project" in celery.tasks


def test_task_eager(tmp_path):
    """
    Run process_project_task eagerly (synchronous, no broker).
    Verifies that all 15 output CSVs are produced.
    """
    from app.services.worker import process_project_task
    from app.db.database import SessionLocal
    from app.db.models import Project
    from app.core.config import PROJECT_DIR

    GTFS_ZIP = Path(__file__).parent / "Resources" / "raw" / "gtfs-20240704-090655.zip"
    if not GTFS_ZIP.exists():
        pytest.skip(f"Test GTFS zip not found: {GTFS_ZIP}")

    TENANT_ID = "test-celery-tenant"

    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True

    db = SessionLocal()
    project = Project(status="pending", parameters={}, tenant_id=TENANT_ID)
    db.add(project)
    db.commit()
    db.refresh(project)
    project_id = project.id
    db.close()

    # Copy to tmp_path so the pipeline's cleanup (zip_path_obj.unlink) does not
    # delete the original test fixture.
    zip_copy = tmp_path / "gtfs_test.zip"
    shutil.copy2(GTFS_ZIP, zip_copy)

    out_dir = PROJECT_DIR / TENANT_ID / project_id / "output"
    try:
        process_project_task.apply(
            kwargs={
                "project_id": project_id,
                "zip_path": str(zip_copy),
                "parameters": {},
            }
        )
        assert out_dir.exists(), "Output directory not created"
        csv_files = list(out_dir.glob("*.csv"))
        assert len(csv_files) == 15, (
            f"Expected 15 CSVs, got {len(csv_files)}: {[f.name for f in csv_files]}"
        )
    finally:
        shutil.rmtree(PROJECT_DIR / TENANT_ID / project_id, ignore_errors=True)
        db2 = SessionLocal()
        db2.query(Project).filter(Project.id == project_id).delete()
        db2.commit()
        db2.close()
        celery.conf.task_always_eager = False
        celery.conf.task_eager_propagates = False
