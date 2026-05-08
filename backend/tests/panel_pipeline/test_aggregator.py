"""Phase 6 derived-indicator aggregator + tier overrides."""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import (
    PanelFeed,
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


def _seed_network(session, slug: str, tier: str = "T1") -> PanelNetwork:
    n = PanelNetwork(
        slug=slug, pan_dataset_id=f"pan-{slug}", display_name=slug, tier=tier
    )
    session.add(n)
    session.flush()
    return n


def _seed_feed(session, network: PanelNetwork, feed_start: datetime) -> PanelFeed:
    f = PanelFeed(
        network_id=network.network_id,
        pan_resource_id=f"r-{network.slug}-{feed_start.isoformat()}",
        published_at=feed_start,
        feed_start_date=feed_start,
        gtfs_url="x.zip",
    )
    session.add(f)
    session.flush()
    return f


def _seed_indicator(
    session, feed: PanelFeed, ind_id: str, value: float | None, unit: str = "km"
) -> None:
    session.add(
        PanelIndicator(feed_id=feed.feed_id, indicator_id=ind_id, value=value, unit=unit)
    )


# ── Task 6.1: zscore + percentile ────────────────────────────────────────────


def test_zscore_pct_5_peer_synthetic(session):
    """5-network peer group, varying KCC. Verify z-score + percentile."""
    from app.services.panel_pipeline.aggregator import recompute_zscore_pct

    networks = [_seed_network(session, f"net{i}") for i in range(5)]
    values = [100.0, 200.0, 300.0, 400.0, 500.0]
    for n, v in zip(networks, values):
        f = _seed_feed(session, n, datetime(2024, 1, 1))
        _seed_indicator(session, f, "prod_kcc_year", v)
    session.commit()

    # Recompute for the middle network (value=300)
    n_updated = recompute_zscore_pct(session, networks[2].network_id)
    assert n_updated >= 1

    middle_feed = (
        session.query(PanelFeed)
        .filter_by(network_id=networks[2].network_id)
        .first()
    )
    derived = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=middle_feed.feed_id, indicator_id="prod_kcc_year")
        .one()
    )
    # mean = 300, stdev = sqrt(((-200)² + (-100)² + 0 + 100² + 200²) / 5) = sqrt(40000) = 200
    assert derived.zscore == pytest.approx(0.0, abs=1e-6)
    # 3 of 5 values ≤ 300 → 60th percentile
    assert derived.percentile == pytest.approx(60.0, abs=0.5)
    assert derived.peer_group_size == 5


def test_zscore_pct_skips_none_values(session):
    """Indicator value=None → exclude from peer group stats."""
    from app.services.panel_pipeline.aggregator import recompute_zscore_pct

    networks = [_seed_network(session, f"net{i}") for i in range(3)]
    f0 = _seed_feed(session, networks[0], datetime(2024, 1, 1))
    f1 = _seed_feed(session, networks[1], datetime(2024, 1, 1))
    f2 = _seed_feed(session, networks[2], datetime(2024, 1, 1))
    _seed_indicator(session, f0, "prod_kcc_year", 100.0)
    _seed_indicator(session, f1, "prod_kcc_year", 200.0)
    session.add(
        PanelIndicator(
            feed_id=f2.feed_id, indicator_id="prod_kcc_year", value=None, unit="km"
        )
    )
    session.commit()

    recompute_zscore_pct(session, networks[0].network_id)
    derived = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=f0.feed_id, indicator_id="prod_kcc_year")
        .one()
    )
    assert derived.peer_group_size == 2  # None excluded


def test_zscore_pct_zero_stdev_handled(session):
    """All peers identical → stdev=0; should set zscore=0 (or None), not crash."""
    from app.services.panel_pipeline.aggregator import recompute_zscore_pct

    networks = [_seed_network(session, f"net{i}") for i in range(3)]
    for n in networks:
        f = _seed_feed(session, n, datetime(2024, 1, 1))
        _seed_indicator(session, f, "prod_kcc_year", 500.0)
    session.commit()
    n_updated = recompute_zscore_pct(session, networks[0].network_id)
    assert n_updated >= 0  # no crash


# ── Task 6.2: YoY ────────────────────────────────────────────────────────────


def test_yoy_delta_with_match(session):
    """Feed at t and t-12m exists → yoy_delta_pct = (cur - prior) / prior × 100."""
    from app.services.panel_pipeline.aggregator import recompute_yoy

    n = _seed_network(session, "lyon")
    f_old = _seed_feed(session, n, datetime(2023, 1, 1))
    f_new = _seed_feed(session, n, datetime(2024, 1, 5))  # ~365d after
    _seed_indicator(session, f_old, "prod_kcc_year", 100.0)
    _seed_indicator(session, f_new, "prod_kcc_year", 110.0)
    session.commit()

    recompute_yoy(session, n.network_id)
    derived = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=f_new.feed_id, indicator_id="prod_kcc_year")
        .one()
    )
    assert derived.yoy_delta_pct == pytest.approx(10.0, abs=0.1)


def test_yoy_delta_no_match_returns_none(session):
    """No feed within ±30d of t-12m → yoy_delta_pct = None."""
    from app.services.panel_pipeline.aggregator import recompute_yoy

    n = _seed_network(session, "lyon")
    f = _seed_feed(session, n, datetime(2024, 1, 1))
    _seed_indicator(session, f, "prod_kcc_year", 100.0)
    session.commit()

    recompute_yoy(session, n.network_id)
    derived = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=f.feed_id, indicator_id="prod_kcc_year")
        .one_or_none()
    )
    if derived is not None:
        assert derived.yoy_delta_pct is None


# ── Task 6.3: post_reorg_delta ───────────────────────────────────────────────


def test_post_reorg_delta_happy_path(session):
    """Reorg flag at feed_b; computes (b - a) / a × 100 per indicator."""
    from app.services.panel_pipeline.aggregator import recompute_post_reorg_delta

    n = _seed_network(session, "lyon")
    f_pre = _seed_feed(session, n, datetime(2024, 6, 1))
    f_post = _seed_feed(session, n, datetime(2024, 9, 1))
    _seed_indicator(session, f_pre, "prod_kcc_year", 100.0)
    _seed_indicator(session, f_post, "prod_kcc_year", 90.0)
    session.add(
        PanelReorgFlag(
            network_id=n.network_id,
            feed_to_id=f_post.feed_id,
            reorg_detected=True,
            reorg_severity="major",
            stop_jaccard=0.6,
            route_jaccard=0.4,
            threshold_version="v1",
        )
    )
    session.commit()

    recompute_post_reorg_delta(session, n.network_id)
    derived = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=f_post.feed_id, indicator_id="prod_kcc_year")
        .one()
    )
    assert derived.post_reorg_delta_pct == pytest.approx(-10.0, abs=0.1)


def test_post_reorg_delta_no_flag_skips(session):
    """No reorg flag → no derived row written for post_reorg_delta."""
    from app.services.panel_pipeline.aggregator import recompute_post_reorg_delta

    n = _seed_network(session, "lyon")
    f = _seed_feed(session, n, datetime(2024, 1, 1))
    _seed_indicator(session, f, "prod_kcc_year", 100.0)
    session.commit()

    n_updated = recompute_post_reorg_delta(session, n.network_id)
    assert n_updated == 0


def test_post_reorg_delta_first_feed_returns_none(session):
    """Reorg flag on the FIRST feed (no prior) → post_reorg_delta=None."""
    from app.services.panel_pipeline.aggregator import recompute_post_reorg_delta

    n = _seed_network(session, "lyon")
    f = _seed_feed(session, n, datetime(2024, 1, 1))
    _seed_indicator(session, f, "prod_kcc_year", 100.0)
    session.add(
        PanelReorgFlag(
            network_id=n.network_id,
            feed_to_id=f.feed_id,
            reorg_detected=True,
            reorg_severity="major",
            stop_jaccard=0.5,
            route_jaccard=0.4,
            threshold_version="v1",
        )
    )
    session.commit()

    recompute_post_reorg_delta(session, n.network_id)
    derived = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=f.feed_id, indicator_id="prod_kcc_year")
        .one_or_none()
    )
    if derived is not None:
        assert derived.post_reorg_delta_pct is None


# ── Task 6.4: tier overrides ─────────────────────────────────────────────────


def test_apply_tier_overrides(session, tmp_path):
    """YAML overrides set tier on listed networks."""
    from app.services.panel_pipeline.peer_groups import apply_tier_overrides

    _seed_network(session, "lyon", tier="T5")  # will be overridden to T1
    _seed_network(session, "rennes", tier="T5")  # → T2
    _seed_network(session, "smalltown", tier="T5")  # not in YAML, stays T5
    session.commit()

    yaml_path = tmp_path / "tiers.yaml"
    yaml_path.write_text(
        "T1: [lyon]\nT2: [rennes]\nR: []\nI: []\n", encoding="utf-8"
    )
    n_updated = apply_tier_overrides(session, yaml_path=yaml_path)
    assert n_updated == 2

    assert session.query(PanelNetwork).filter_by(slug="lyon").one().tier == "T1"
    assert session.query(PanelNetwork).filter_by(slug="rennes").one().tier == "T2"
    assert session.query(PanelNetwork).filter_by(slug="smalltown").one().tier == "T5"


def test_apply_tier_overrides_uses_default_yaml_when_path_omitted(session, tmp_path):
    """Calling without yaml_path uses the bundled default network_tier_overrides.yaml."""
    from app.services.panel_pipeline.peer_groups import apply_tier_overrides

    _seed_network(session, "lyon", tier="T5")
    session.commit()

    n_updated = apply_tier_overrides(session)
    # The bundled YAML lists 'lyon' as T1
    assert n_updated >= 1
    assert session.query(PanelNetwork).filter_by(slug="lyon").one().tier == "T1"
