"""Phase 7 Task 7.1: run_panel_pipeline orchestrator end-to-end coverage.

Verifies:
    - Production path writes 38 PanelIndicator + 1 PanelQuality row per feed.
    - Unknown feed_id raises ValueError.
    - Idempotency: re-running on the same feed_id updates rows (no duplicates).
    - methodology_commit fallback to a non-empty string when no env / repo.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    PanelFeed,
    PanelIndicator,
    PanelNetwork,
    PanelQuality,
)


FIXTURE_ZIP = (
    Path(__file__).resolve().parents[1] / "Resources" / "raw" / "SEM-GTFS(2).zip"
)


class _SessionContext:
    """Context-manager wrapper that yields a pre-built Session.

    The orchestrator uses ``with SessionLocal() as session:`` blocks; in tests
    we patch SessionLocal to return one of these so all operations land on the
    same in-memory DB the test fixture seeded.
    """

    def __init__(self, session) -> None:
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *_args, **_kwargs) -> None:
        # Don't close — the fixture owns the session lifecycle.
        return None


@pytest.fixture()
def session_with_feed():
    """In-memory DB seeded with one network + one feed pointing at the SEM fixture."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    n = PanelNetwork(
        slug="grenoble-sem",
        pan_dataset_id="pan-sem",
        display_name="SMTC",
        tier="T2",
        population=445_000,
        area_km2=541.0,
    )
    s.add(n)
    s.flush()
    f = PanelFeed(
        network_id=n.network_id,
        pan_resource_id="r1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 1, 1),
        gtfs_url="file://" + str(FIXTURE_ZIP),
        r2_path=str(FIXTURE_ZIP),  # use fixture as the local cache
    )
    s.add(f)
    s.commit()
    yield s, n, f
    s.close()
    engine.dispose()


def _patch_session_local(monkeypatch, session) -> None:
    """Patch every import path of SessionLocal that run.py uses to a fake context."""
    from app.db import database as db_module

    monkeypatch.setattr(
        db_module, "SessionLocal", lambda: _SessionContext(session)
    )


def test_run_panel_pipeline_writes_38_indicators(session_with_feed, monkeypatch):
    """End-to-end: pipeline writes 38 indicator rows + 1 quality row + flips status to ok."""
    s, _n, f = session_with_feed
    _patch_session_local(monkeypatch, s)

    from app.services.panel_pipeline import run as run_module

    run_module.run_panel_pipeline(f.feed_id)

    # 38 indicator rows (some cov_* may be None when carroyage missing — still 38 rows).
    assert (
        s.query(PanelIndicator).filter_by(feed_id=f.feed_id).count() == 38
    )
    # 1 quality row.
    assert s.query(PanelQuality).filter_by(feed_id=f.feed_id).count() == 1
    # Status flipped to ok.
    s.refresh(f)
    assert f.process_status == "ok"


def test_run_panel_pipeline_unknown_feed_raises(session_with_feed, monkeypatch):
    """feed_id not in DB → ValueError with 'not found' in the message."""
    s, _n, _f = session_with_feed
    _patch_session_local(monkeypatch, s)

    from app.services.panel_pipeline import run as run_module

    with pytest.raises(ValueError, match="not found"):
        run_module.run_panel_pipeline("nonexistent-id")


def test_run_panel_pipeline_idempotent(session_with_feed, monkeypatch):
    """Re-running on the same feed_id updates existing rows; never duplicates."""
    s, _n, f = session_with_feed
    _patch_session_local(monkeypatch, s)

    from app.services.panel_pipeline import run as run_module

    run_module.run_panel_pipeline(f.feed_id)
    count_after_first = (
        s.query(PanelIndicator).filter_by(feed_id=f.feed_id).count()
    )
    quality_after_first = (
        s.query(PanelQuality).filter_by(feed_id=f.feed_id).count()
    )

    run_module.run_panel_pipeline(f.feed_id)
    count_after_second = (
        s.query(PanelIndicator).filter_by(feed_id=f.feed_id).count()
    )
    quality_after_second = (
        s.query(PanelQuality).filter_by(feed_id=f.feed_id).count()
    )

    assert count_after_first == count_after_second == 38
    assert quality_after_first == quality_after_second == 1


def test_resolve_methodology_commit_falls_back():
    """No env var → returns a non-empty string ('unknown' or repo HEAD)."""
    from app.services.panel_pipeline.run import _resolve_methodology_commit

    env_backup = os.environ.pop("METHODOLOGY_COMMIT", None)
    try:
        commit = _resolve_methodology_commit()
        assert commit  # non-empty string
        assert isinstance(commit, str)
    finally:
        if env_backup is not None:
            os.environ["METHODOLOGY_COMMIT"] = env_backup
