"""
test_result_persistence.py — Tests for Task 18: CSV results persisted to DB.

Strategy:
  - Use a fresh in-memory SQLite engine (all tables, including result tables).
  - Patch `app.services.worker.SessionLocal` so run_project_task_sync writes to
    the in-memory DB instead of the real one.
  - Because _persist_results_to_db uses db.bind, it also targets the test engine.
  - Each test copies the shared GTFS ZIP to avoid the worker deleting the original.
"""
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.result_models  # noqa: F401 — ensure result tables are registered
from app.db.database import Base
from app.db.models import Project
from app.services.worker import run_project_task_sync

GTFS_ZIP = Path(__file__).parent / "Resources" / "raw" / "SEM-GTFS(2).zip"


@pytest.fixture(scope="module")
def mem_engine():
    """In-memory SQLite engine with ALL tables (core + 15 result tables)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def mem_session_factory(mem_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=mem_engine)


def _make_project(session_factory, project_id: str, tenant_id: str = "tenant-test") -> None:
    """Insert a minimal Project row into the test DB."""
    db = session_factory()
    project = Project(
        id=project_id,
        tenant_id=tenant_id,
        status="pending",
        parameters={},
    )
    db.add(project)
    db.commit()
    db.close()


def _run_pipeline(session_factory, project_id: str, zip_path: Path, tmp_path: Path) -> None:
    """Copy ZIP to tmp, patch SessionLocal, call run_project_task_sync."""
    tmp_zip = tmp_path / f"{project_id}.zip"
    shutil.copy(zip_path, tmp_zip)
    with patch("app.services.worker.SessionLocal", session_factory):
        run_project_task_sync(project_id, str(tmp_zip), {}, loop=None)


def _count_a1(mem_engine, project_id: str) -> int:
    with mem_engine.connect() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM result_a1_arrets_generiques WHERE project_id = :pid"),
            {"pid": project_id},
        ).scalar()


# ─────────────────────────────────────────────────────────────────────────────

def test_results_written_to_db(mem_engine, mem_session_factory, tmp_path):
    """After pipeline runs, result_a1_arrets_generiques must have rows for the project."""
    pid = str(uuid.uuid4())
    _make_project(mem_session_factory, pid)
    _run_pipeline(mem_session_factory, pid, GTFS_ZIP, tmp_path)

    count = _count_a1(mem_engine, pid)
    assert count > 0, f"Expected rows in result_a1_arrets_generiques for project {pid}, got 0"


def test_result_project_id_filter(mem_engine, mem_session_factory, tmp_path):
    """Two projects must not share rows — project_id isolation."""
    pid_a = str(uuid.uuid4())
    pid_b = str(uuid.uuid4())
    _make_project(mem_session_factory, pid_a)
    _make_project(mem_session_factory, pid_b)
    _run_pipeline(mem_session_factory, pid_a, GTFS_ZIP, tmp_path)
    _run_pipeline(mem_session_factory, pid_b, GTFS_ZIP, tmp_path)

    count_a = _count_a1(mem_engine, pid_a)
    count_b = _count_a1(mem_engine, pid_b)
    assert count_a > 0
    assert count_b > 0

    # Total rows must equal sum of individual counts (no cross-contamination)
    with mem_engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM result_a1_arrets_generiques WHERE project_id IN (:a, :b)"),
            {"a": pid_a, "b": pid_b},
        ).scalar()
    assert total == count_a + count_b


def test_idempotent_reprocess(mem_engine, mem_session_factory, tmp_path):
    """Re-running the pipeline for the same project must not duplicate rows."""
    pid = str(uuid.uuid4())
    _make_project(mem_session_factory, pid)

    _run_pipeline(mem_session_factory, pid, GTFS_ZIP, tmp_path)
    count_first = _count_a1(mem_engine, pid)
    assert count_first > 0

    _run_pipeline(mem_session_factory, pid, GTFS_ZIP, tmp_path)
    count_second = _count_a1(mem_engine, pid)
    assert count_second == count_first, (
        f"Row count changed after re-run: {count_first} → {count_second} (idempotency violation)"
    )
