"""Idempotent persistence for FeedDiff + ReorgVerdict."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import PanelFeed, PanelFeedDiff, PanelNetwork, PanelReorgFlag
from app.services.panel_pipeline.diff.feed_diff import FeedDiff
from app.services.panel_pipeline.diff.persist import persist_diff_and_flag
from app.services.panel_pipeline.diff.reorg_detect import ReorgVerdict


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def network_pair(session):
    network = PanelNetwork(slug="lyon", pan_dataset_id="pan-lyon", display_name="TCL")
    session.add(network)
    session.flush()
    feed_a = PanelFeed(
        network_id=network.network_id, pan_resource_id="r1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 1, 1), gtfs_url="a.zip",
    )
    feed_b = PanelFeed(
        network_id=network.network_id, pan_resource_id="r2",
        published_at=datetime(2024, 9, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 9, 1), gtfs_url="b.zip",
    )
    session.add_all([feed_a, feed_b])
    session.commit()
    return network, feed_a, feed_b


def _make_diff(stop_j: float = 0.95, route_j: float = 0.27) -> FeedDiff:
    return FeedDiff(
        stops_added=["S1"], stops_removed=[], stops_modified={},
        routes_added=["R1"], routes_removed=[], routes_modified={},
        stop_jaccard=stop_j, route_jaccard=route_j,
    )


def _make_verdict(detected: bool = True, severity: str | None = "massive",
                  stop_j: float = 0.95, route_j: float = 0.27) -> ReorgVerdict:
    return ReorgVerdict(
        detected=detected, severity=severity,
        stop_jaccard=stop_j, route_jaccard=route_j,
        threshold_version="v1-test",
    )


def test_persist_writes_both_rows(session, network_pair):
    network, fa, fb = network_pair
    persist_diff_and_flag(session, network.network_id, fa.feed_id, fb.feed_id,
                          _make_diff(), _make_verdict())
    assert session.query(PanelFeedDiff).count() == 1
    assert session.query(PanelReorgFlag).count() == 1
    diff_row = session.query(PanelFeedDiff).one()
    assert diff_row.stops_added == ["S1"]
    assert diff_row.stop_jaccard == 0.95
    assert diff_row.route_jaccard == 0.27
    flag_row = session.query(PanelReorgFlag).one()
    assert flag_row.reorg_detected is True
    assert flag_row.reorg_severity == "massive"
    assert flag_row.threshold_version == "v1-test"


def test_persist_idempotent_on_repeat_call(session, network_pair):
    """Calling persist_diff_and_flag twice with the same (from, to) does not duplicate."""
    network, fa, fb = network_pair
    persist_diff_and_flag(session, network.network_id, fa.feed_id, fb.feed_id,
                          _make_diff(), _make_verdict())
    persist_diff_and_flag(session, network.network_id, fa.feed_id, fb.feed_id,
                          _make_diff(), _make_verdict())
    assert session.query(PanelFeedDiff).count() == 1
    assert session.query(PanelReorgFlag).count() == 1


def test_persist_no_reorg_writes_flag_with_detected_false(session, network_pair):
    """Even when no reorg, a flag row is recorded for audit / lineage purposes."""
    network, fa, fb = network_pair
    persist_diff_and_flag(
        session, network.network_id, fa.feed_id, fb.feed_id,
        _make_diff(stop_j=1.0, route_j=1.0),
        _make_verdict(detected=False, severity=None, stop_j=1.0, route_j=1.0),
    )
    assert session.query(PanelReorgFlag).count() == 1
    flag = session.query(PanelReorgFlag).one()
    assert flag.reorg_detected is False
    assert flag.reorg_severity is None


def test_persist_different_pairs_create_separate_rows(session, network_pair):
    """Two different feed pairs in the same network → two diff rows."""
    network, fa, fb = network_pair
    # Add a third feed
    feed_c = PanelFeed(
        network_id=network.network_id, pan_resource_id="r3",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2025, 1, 1), gtfs_url="c.zip",
    )
    session.add(feed_c)
    session.commit()
    persist_diff_and_flag(session, network.network_id, fa.feed_id, fb.feed_id,
                          _make_diff(), _make_verdict())
    persist_diff_and_flag(session, network.network_id, fb.feed_id, feed_c.feed_id,
                          _make_diff(stop_j=0.85, route_j=0.85),
                          _make_verdict(detected=False, severity=None,
                                        stop_j=0.85, route_j=0.85))
    assert session.query(PanelFeedDiff).count() == 2
    assert session.query(PanelReorgFlag).count() == 2
