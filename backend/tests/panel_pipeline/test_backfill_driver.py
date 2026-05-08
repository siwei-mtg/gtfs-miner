"""Plan 2 Task 7.3 — backfill driver enumeration."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/scripts is importable as a package
BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))


def test_enumerate_pending_feeds():
    """Pending and failed feeds are picked up; ok feeds are skipped."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.database import Base
    from app.db.models import PanelFeed, PanelNetwork

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()

    n = PanelNetwork(slug="x", pan_dataset_id="px", display_name="X")
    s.add(n)
    s.flush()

    f1 = PanelFeed(
        network_id=n.network_id,
        pan_resource_id="r1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 1, 1),
        gtfs_url="x",
        process_status="pending",
    )
    f2 = PanelFeed(
        network_id=n.network_id,
        pan_resource_id="r2",
        published_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 2, 1),
        gtfs_url="x",
        process_status="ok",
    )
    f3 = PanelFeed(
        network_id=n.network_id,
        pan_resource_id="r3",
        published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 3, 1),
        gtfs_url="x",
        process_status="failed",
    )
    s.add_all([f1, f2, f3])
    s.commit()

    from scripts.run_panel_backfill import enumerate_pending_feeds

    feed_ids = enumerate_pending_feeds(s)
    assert f1.feed_id in feed_ids
    assert f3.feed_id in feed_ids
    assert f2.feed_id not in feed_ids
    s.close()
