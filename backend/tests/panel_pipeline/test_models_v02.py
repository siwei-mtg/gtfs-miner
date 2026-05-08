"""Spec §6.3.2 v0.2 schema additions — round-trip insert tests on in-memory SQLite.

Adds:
    panel_feed_diffs, panel_reorg_flags, panel_dsp_events tables
    panel_indicators.error_margin_pct, panel_indicators.methodology_commit
    panel_indicators_derived.post_reorg_delta_pct, panel_indicators_derived.methodology_commit
    panel_networks.has_metro
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    PanelDspEvent,
    PanelFeed,
    PanelFeedDiff,
    PanelIndicator,
    PanelIndicatorDerived,
    PanelNetwork,
    PanelReorgFlag,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def network_with_two_feeds(session):
    network = PanelNetwork(
        slug="lyon",
        pan_dataset_id="pan-lyon",
        display_name="TCL",
        tier="T1",
        population=1_420_000,
        area_km2=538.0,
    )
    session.add(network)
    session.flush()
    feed_a = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="r1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 1, 1),
        gtfs_url="https://example.com/a.zip",
    )
    feed_b = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="r2",
        published_at=datetime(2024, 9, 1, tzinfo=timezone.utc),
        feed_start_date=datetime(2024, 9, 1),
        gtfs_url="https://example.com/b.zip",
    )
    session.add_all([feed_a, feed_b])
    session.commit()
    return network, feed_a, feed_b


def test_panel_feed_diff_roundtrip(session, network_with_two_feeds):
    network, feed_a, feed_b = network_with_two_feeds
    diff = PanelFeedDiff(
        network_id=network.network_id,
        feed_from_id=feed_a.feed_id,
        feed_to_id=feed_b.feed_id,
        stops_added=["S100", "S101"],
        stops_removed=[],
        stops_modified={},
        routes_added=["R5"],
        routes_removed=["R3"],
        routes_modified={},
        stop_jaccard=0.95,
        route_jaccard=0.27,
    )
    session.add(diff)
    session.commit()
    fetched = session.query(PanelFeedDiff).first()
    assert fetched.stops_added == ["S100", "S101"]
    assert fetched.route_jaccard == pytest.approx(0.27)


def test_panel_feed_diff_unique_pair(session, network_with_two_feeds):
    """UNIQUE (feed_from_id, feed_to_id) — second insert fails."""
    network, feed_a, feed_b = network_with_two_feeds
    session.add(PanelFeedDiff(
        network_id=network.network_id,
        feed_from_id=feed_a.feed_id, feed_to_id=feed_b.feed_id,
        stop_jaccard=1.0, route_jaccard=1.0,
    ))
    session.commit()
    session.add(PanelFeedDiff(
        network_id=network.network_id,
        feed_from_id=feed_a.feed_id, feed_to_id=feed_b.feed_id,
        stop_jaccard=0.5, route_jaccard=0.5,
    ))
    with pytest.raises(Exception):
        session.commit()
    session.rollback()


def test_panel_reorg_flag_roundtrip(session, network_with_two_feeds):
    network, _, feed_b = network_with_two_feeds
    flag = PanelReorgFlag(
        network_id=network.network_id,
        feed_to_id=feed_b.feed_id,
        reorg_detected=True,
        reorg_severity="major",
        stop_jaccard=0.62,
        route_jaccard=0.40,
        threshold_version="v1",
    )
    session.add(flag)
    session.commit()
    assert session.query(PanelReorgFlag).count() == 1
    assert session.query(PanelReorgFlag).one().reorg_severity == "major"


def test_panel_dsp_event_roundtrip(session, network_with_two_feeds):
    network, *_ = network_with_two_feeds
    evt = PanelDspEvent(
        network_id=network.network_id,
        event_type="contract_started",
        event_date=datetime(2017, 9, 1),
        operator_after="Keolis",
        source="BOAMP",
        contributor="wei",
        csv_row_hash="abc123",
    )
    session.add(evt)
    session.commit()
    assert session.query(PanelDspEvent).count() == 1


def test_panel_dsp_event_unique_hash(session, network_with_two_feeds):
    """csv_row_hash is UNIQUE — second row with same hash fails."""
    network, *_ = network_with_two_feeds
    session.add(PanelDspEvent(
        network_id=network.network_id, event_type="contract_started",
        event_date=datetime(2017, 9, 1), source="BOAMP",
        contributor="wei", csv_row_hash="dup",
    ))
    session.commit()
    session.add(PanelDspEvent(
        network_id=network.network_id, event_type="amendment",
        event_date=datetime(2018, 1, 1), source="press",
        contributor="alice", csv_row_hash="dup",
    ))
    with pytest.raises(Exception):
        session.commit()
    session.rollback()


def test_audit_columns_on_indicators(session, network_with_two_feeds):
    _, feed_a, _ = network_with_two_feeds
    ind = PanelIndicator(
        feed_id=feed_a.feed_id,
        indicator_id="prod_kcc_year",
        value=24_300_000.0,
        unit="km/year",
        error_margin_pct=2.1,
        methodology_commit="a3f2c1d",
    )
    session.add(ind)
    session.commit()
    fetched = session.query(PanelIndicator).first()
    assert fetched.error_margin_pct == pytest.approx(2.1)
    assert fetched.methodology_commit == "a3f2c1d"


def test_post_reorg_delta_column_on_derived(session, network_with_two_feeds):
    _, _, feed_b = network_with_two_feeds
    der = PanelIndicatorDerived(
        feed_id=feed_b.feed_id,
        indicator_id="prod_kcc_year",
        post_reorg_delta_pct=-3.0,
        methodology_commit="a3f2c1d",
    )
    session.add(der)
    session.commit()
    fetched = session.query(PanelIndicatorDerived).first()
    assert fetched.post_reorg_delta_pct == pytest.approx(-3.0)
    assert fetched.methodology_commit == "a3f2c1d"


def test_has_metro_column_on_network(session):
    n = PanelNetwork(
        slug="paris",
        pan_dataset_id="pan-paris",
        display_name="IDFM",
        has_metro=True,
    )
    session.add(n)
    session.commit()
    fetched = session.query(PanelNetwork).filter_by(slug="paris").one()
    assert fetched.has_metro is True


def test_has_metro_default_false(session):
    """Existing networks without explicit has_metro default to False."""
    n = PanelNetwork(
        slug="strasbourg",
        pan_dataset_id="pan-strasbourg",
        display_name="CTS",
    )
    session.add(n)
    session.commit()
    assert session.query(PanelNetwork).filter_by(slug="strasbourg").one().has_metro is False
