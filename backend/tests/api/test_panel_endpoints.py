"""Plan 2 Task 7.4 — panel API endpoints happy-path tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import (
    PanelFeed,
    PanelIndicator,
    PanelNetwork,
    PanelQuality,
)


@pytest.fixture()
def seeded_db(test_db):
    """Seed the in-memory DB with one network + one feed + minimal indicators.

    The ``test_engine`` fixture is session-scoped, so this seed is also
    idempotent — if a previous test in the same session already inserted
    ``slug='lyon'``, we reuse it instead of duplicating.
    """
    n = test_db.query(PanelNetwork).filter_by(slug="lyon").one_or_none()
    if n is None:
        n = PanelNetwork(
            slug="lyon",
            pan_dataset_id="pan-lyon",
            display_name="TCL",
            tier="T1",
            population=1_420_000,
            area_km2=538.0,
        )
        test_db.add(n)
        test_db.flush()
    f = (
        test_db.query(PanelFeed)
        .filter_by(network_id=n.network_id, pan_resource_id="r1")
        .one_or_none()
    )
    if f is None:
        f = PanelFeed(
            network_id=n.network_id,
            pan_resource_id="r1",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            feed_start_date=datetime(2024, 1, 1),
            gtfs_url="https://x.zip",
        )
        test_db.add(f)
        test_db.flush()
    if (
        test_db.query(PanelIndicator)
        .filter_by(feed_id=f.feed_id, indicator_id="prod_kcc_year")
        .one_or_none()
        is None
    ):
        test_db.add(
            PanelIndicator(
                feed_id=f.feed_id,
                indicator_id="prod_kcc_year",
                value=24_300_000.0,
                unit="km",
                error_margin_pct=2.1,
                methodology_commit="a3f2c1d",
            )
        )
    if (
        test_db.query(PanelQuality)
        .filter_by(feed_id=f.feed_id)
        .one_or_none()
        is None
    ):
        test_db.add(
            PanelQuality(
                feed_id=f.feed_id,
                overall_score=87.0,
                overall_grade="A-",
            )
        )
    test_db.commit()
    return test_db


def test_list_networks(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/networks")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "public, max-age=3600, s-maxage=86400"
    j = r.json()
    assert j["total"] == 1
    assert j["networks"][0]["slug"] == "lyon"


def test_get_network_detail(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/networks/lyon")
    assert r.status_code == 200
    j = r.json()
    assert j["slug"] == "lyon"
    assert "prod_kcc_year" in j["indicators"]
    sample = j["indicators"]["prod_kcc_year"]
    assert sample["value"] == 24_300_000.0
    assert sample["error_margin_pct"] == 2.1
    assert sample["methodology_commit"] == "a3f2c1d"
    assert sample["methodology_url"].startswith(
        "https://github.com/compare-transit/methodology/blob/a3f2c1d/"
    )


def test_get_network_404(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/networks/does-not-exist")
    assert r.status_code == 404


def test_network_history(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/networks/lyon/history")
    assert r.status_code == 200
    j = r.json()
    assert j["slug"] == "lyon"
    assert isinstance(j["points"], list)


def test_indicator_ranking(isolated_client, seeded_db):
    r = isolated_client.get(
        "/api/v1/panel/indicators/prod_kcc_year/ranking"
    )
    assert r.status_code == 200
    j = r.json()
    assert j["indicator_id"] == "prod_kcc_year"
    assert len(j["rankings"]) == 1
    assert j["rankings"][0]["slug"] == "lyon"


def test_quality_ranking(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/quality/ranking")
    assert r.status_code == 200
    j = r.json()
    assert any(x["slug"] == "lyon" for x in j["rankings"])


def test_dsp_events_per_network(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/networks/lyon/dsp-events")
    assert r.status_code == 200
    j = r.json()
    assert j["slug"] == "lyon"
    assert isinstance(j["events"], list)


def test_reorg_events_per_network(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/networks/lyon/reorg-events")
    assert r.status_code == 200
    j = r.json()
    assert j["slug"] == "lyon"
    assert isinstance(j["events"], list)


def test_reorg_events_global(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/reorg-events/global")
    assert r.status_code == 200
    j = r.json()
    assert "events" in j


def test_dsp_events_global(isolated_client, seeded_db):
    r = isolated_client.get("/api/v1/panel/dsp-events/global")
    assert r.status_code == 200
    j = r.json()
    assert "events" in j
