"""Spec §6.3 storage schema — round-trip insert tests on in-memory SQLite."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    PanelFeed,
    PanelIndicator,
    PanelIndicatorDerived,
    PanelNetwork,
    PanelPeerGroup,
    PanelQuality,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_panel_network_roundtrip(session) -> None:
    n = PanelNetwork(
        slug="lyon",
        pan_dataset_id="abc-123",
        display_name="Métropole de Lyon — TCL",
        aom_id="69123",
        tier="T1",
        population=1_420_000,
        area_km2=538.0,
    )
    session.add(n)
    session.commit()
    fetched = session.query(PanelNetwork).filter_by(slug="lyon").one()
    assert fetched.tier == "T1"
    assert fetched.population == 1_420_000


def test_panel_feed_indicator_chain(session) -> None:
    network = PanelNetwork(
        slug="t",
        pan_dataset_id="t",
        display_name="t",
        aom_id="t",
        tier="T5",
        population=10000,
        area_km2=1.0,
    )
    session.add(network)
    session.commit()

    feed = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="r1",
        pan_resource_history_id="rh1",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 1, 1),
        feed_info_sha256="abcd" * 16,
        feed_info_source="feed_info",
        gtfs_url="https://example/feed.zip",
        filesize=1024 * 500,
        process_status="done",
    )
    session.add(feed)
    session.commit()

    ind = PanelIndicator(
        feed_id=feed.feed_id,
        indicator_id="prod_kcc_year",
        value=12345.6,
        unit="km",
    )
    session.add(ind)
    session.commit()

    fetched = session.query(PanelIndicator).filter_by(indicator_id="prod_kcc_year").one()
    assert fetched.value == pytest.approx(12345.6)


def test_panel_quality_jsonb(session) -> None:
    network = PanelNetwork(
        slug="q",
        pan_dataset_id="q",
        display_name="q",
        aom_id="q",
        tier="T5",
        population=10000,
        area_km2=1.0,
    )
    session.add(network)
    session.commit()
    feed = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="qr1",
        pan_resource_history_id="qrh1",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 6, 1),
        feed_info_sha256="ef00" * 16,
        feed_info_source="feed_info",
        gtfs_url="https://example/q.zip",
        process_status="done",
    )
    session.add(feed)
    session.commit()

    q = PanelQuality(
        feed_id=feed.feed_id,
        validator_errors={"system_errors": [], "notices": []},
        overall_grade="A-",
        overall_score=87.0,
    )
    session.add(q)
    session.commit()
    fetched = session.query(PanelQuality).one()
    assert fetched.overall_grade == "A-"
    assert "notices" in fetched.validator_errors


def test_panel_indicator_derived_roundtrip(session) -> None:
    network = PanelNetwork(
        slug="d", pan_dataset_id="d", display_name="d",
        aom_id="d", tier="T3", population=300_000, area_km2=120.0,
    )
    session.add(network)
    session.commit()
    feed = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="dr1",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 3, 1),
        gtfs_url="https://example/d.zip",
    )
    session.add(feed)
    session.commit()
    derived = PanelIndicatorDerived(
        feed_id=feed.feed_id,
        indicator_id="dens_kcc_capita",
        zscore=1.42,
        percentile=87.5,
        yoy_delta_pct=4.2,
        peer_group_size=12,
    )
    session.add(derived)
    session.commit()
    fetched = session.query(PanelIndicatorDerived).one()
    assert fetched.zscore == pytest.approx(1.42)
    assert fetched.peer_group_size == 12


def test_panel_peer_group_roundtrip(session) -> None:
    pg = PanelPeerGroup(
        group_id="T1",
        display_name="Grandes métropoles avec métro",
        definition={"population_min": 1_000_000, "requires_mode": "metro"},
        member_count=5,
    )
    session.add(pg)
    session.commit()
    fetched = session.query(PanelPeerGroup).filter_by(group_id="T1").one()
    assert fetched.member_count == 5
    assert fetched.definition["population_min"] == 1_000_000


def test_panel_feed_dedup_unique_constraint(session) -> None:
    """Spec §6.3: UNIQUE(network_id, feed_start_date) enforces dedup at DB level."""
    network = PanelNetwork(
        slug="u", pan_dataset_id="u", display_name="u",
        aom_id="u", tier="T5", population=10000, area_km2=1.0,
    )
    session.add(network)
    session.commit()
    feed1 = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="u1",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 1, 1),
        gtfs_url="https://example/u1.zip",
    )
    session.add(feed1)
    session.commit()
    # Second feed with same network_id + feed_start_date should violate UNIQUE
    feed2 = PanelFeed(
        network_id=network.network_id,
        pan_resource_id="u2",
        published_at=datetime.now(timezone.utc),
        feed_start_date=datetime(2025, 1, 1),
        gtfs_url="https://example/u2.zip",
    )
    session.add(feed2)
    with pytest.raises(Exception):  # IntegrityError
        session.commit()
    session.rollback()
