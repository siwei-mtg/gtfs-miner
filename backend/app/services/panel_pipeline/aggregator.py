"""Derived indicators: z-score, percentile, YoY delta, post_reorg_delta.

Spec §5.2 + Plan 2 §6.3 derived layer. Runs AFTER panel_pipeline.run writes
raw `panel_indicators` rows; populates `panel_indicators_derived`.
"""
from __future__ import annotations

import statistics
from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    PanelFeed,
    PanelIndicator,
    PanelIndicatorDerived,
    PanelNetwork,
    PanelReorgFlag,
)


# ────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────


def _latest_feed(session: Session, network_id: str) -> PanelFeed | None:
    """Return the most recent PanelFeed for a network, by feed_start_date."""
    return (
        session.query(PanelFeed)
        .filter_by(network_id=network_id)
        .order_by(PanelFeed.feed_start_date.desc())
        .first()
    )


def _upsert_derived(
    session: Session,
    feed_id: str,
    indicator_id: str,
    methodology_commit: str = "",
    **fields,
) -> None:
    """Insert or update a PanelIndicatorDerived row, merging the given fields."""
    existing = (
        session.query(PanelIndicatorDerived)
        .filter_by(feed_id=feed_id, indicator_id=indicator_id)
        .one_or_none()
    )
    if existing is None:
        session.add(
            PanelIndicatorDerived(
                feed_id=feed_id,
                indicator_id=indicator_id,
                methodology_commit=methodology_commit,
                **fields,
            )
        )
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
        if methodology_commit:
            existing.methodology_commit = methodology_commit


# ────────────────────────────────────────────────────────
# Task 6.1: z-score + percentile
# ────────────────────────────────────────────────────────


def recompute_zscore_pct(
    session: Session,
    network_id: str,
    methodology_commit: str = "",
) -> int:
    """Recompute z-score + percentile across same-tier peers for this network's
    latest feed.

    Algorithm:
        1. Load this network's tier (from PanelNetwork)
        2. For each peer in the same tier, find the latest feed
        3. For each (indicator_id, peer values across the tier):
           - mean, stdev (population)
           - this network's z-score = (value - mean) / stdev (0 if stdev=0)
           - this network's percentile = (count of peer values ≤ value) / count × 100
        4. Upsert (feed_id, indicator_id) row with zscore, percentile, peer_group_size

    Returns: number of indicator rows upserted.
    """
    me = session.get(PanelNetwork, network_id)
    if me is None or me.tier is None:
        return 0

    peers = session.query(PanelNetwork).filter(PanelNetwork.tier == me.tier).all()
    peer_latest: dict[str, PanelFeed] = {}
    for p in peers:
        f = _latest_feed(session, p.network_id)
        if f is not None:
            peer_latest[p.network_id] = f

    my_feed = peer_latest.get(network_id)
    if my_feed is None:
        return 0

    # All distinct indicator IDs touched by these peers
    feed_ids = [f.feed_id for f in peer_latest.values()]
    indicator_ids = [
        r[0]
        for r in session.query(PanelIndicator.indicator_id)
        .filter(PanelIndicator.feed_id.in_(feed_ids))
        .distinct()
    ]

    n_updated = 0
    for ind_id in indicator_ids:
        peer_values: dict[str, float] = {}
        for nid, feed in peer_latest.items():
            row = (
                session.query(PanelIndicator.value)
                .filter_by(feed_id=feed.feed_id, indicator_id=ind_id)
                .scalar()
            )
            if row is not None:
                peer_values[nid] = float(row)

        if not peer_values or network_id not in peer_values:
            continue

        my_val = peer_values[network_id]
        values = list(peer_values.values())
        if len(values) >= 2:
            mean = statistics.mean(values)
            stdev = statistics.pstdev(values)
            zscore = (my_val - mean) / stdev if stdev > 0 else 0.0
        else:
            zscore = 0.0

        # Percentile: % of peer values ≤ my_val
        pct = 100.0 * sum(1 for v in values if v <= my_val) / len(values)

        _upsert_derived(
            session,
            my_feed.feed_id,
            ind_id,
            methodology_commit=methodology_commit,
            zscore=zscore,
            percentile=pct,
            peer_group_size=len(peer_values),
        )
        n_updated += 1

    session.commit()
    return n_updated


# ────────────────────────────────────────────────────────
# Task 6.2: YoY delta
# ────────────────────────────────────────────────────────


def recompute_yoy(
    session: Session,
    network_id: str,
    methodology_commit: str = "",
) -> int:
    """For latest feed of network, compute YoY delta = (current - t-12m) / t-12m × 100.

    Match: feed within ±30 days of (current.feed_start_date - 365 days).
    No match → yoy_delta_pct = None (UPSERT writes None, doesn't skip).

    Returns: number of indicator rows upserted (one per indicator on the latest feed).
    """
    feeds = (
        session.query(PanelFeed)
        .filter_by(network_id=network_id)
        .order_by(PanelFeed.feed_start_date.desc())
        .all()
    )
    if not feeds:
        return 0

    cur = feeds[0]
    target = cur.feed_start_date - timedelta(days=365)
    window_low = target - timedelta(days=30)
    window_high = target + timedelta(days=30)

    prior = next(
        (f for f in feeds if window_low <= f.feed_start_date <= window_high),
        None,
    )

    cur_inds = session.query(PanelIndicator).filter_by(feed_id=cur.feed_id).all()
    n_updated = 0
    for ind in cur_inds:
        delta_pct: float | None = None
        if prior is not None:
            prior_val = (
                session.query(PanelIndicator.value)
                .filter_by(feed_id=prior.feed_id, indicator_id=ind.indicator_id)
                .scalar()
            )
            if prior_val is not None and float(prior_val) != 0 and ind.value is not None:
                delta_pct = (
                    (float(ind.value) - float(prior_val)) / float(prior_val) * 100.0
                )

        _upsert_derived(
            session,
            cur.feed_id,
            ind.indicator_id,
            methodology_commit=methodology_commit,
            yoy_delta_pct=delta_pct,
        )
        n_updated += 1

    session.commit()
    return n_updated


# ────────────────────────────────────────────────────────
# Task 6.3: post_reorg_delta
# ────────────────────────────────────────────────────────


def recompute_post_reorg_delta(
    session: Session,
    network_id: str,
    methodology_commit: str = "",
) -> int:
    """For each PanelReorgFlag(network_id, feed_to_id) where reorg_detected=True,
    compute post_reorg_delta_pct per indicator:

        delta = (value_at_feed_to - value_at_feed_immediately_before) / value_before × 100

    Edge cases (write None, never crash):
        - No prior feed exists (reorg flag on first feed) → delta = None
        - Either prior or current indicator value is None → delta = None
        - prior indicator value is 0 → delta = None (avoid div-by-zero)

    Returns: number of indicator rows upserted across all reorg flags.
    """
    flags = (
        session.query(PanelReorgFlag)
        .filter_by(network_id=network_id, reorg_detected=True)
        .all()
    )
    if not flags:
        return 0

    feeds = (
        session.query(PanelFeed)
        .filter_by(network_id=network_id)
        .order_by(PanelFeed.feed_start_date)
        .all()
    )
    feed_by_id = {f.feed_id: f for f in feeds}

    n_updated = 0
    for flag in flags:
        post = feed_by_id.get(flag.feed_to_id)
        if post is None:
            continue

        # Find feed immediately prior by feed_start_date (feeds list is ascending)
        prior: PanelFeed | None = None
        for f in feeds:
            if f.feed_start_date < post.feed_start_date:
                prior = f
            else:
                break

        cur_inds = session.query(PanelIndicator).filter_by(feed_id=post.feed_id).all()
        for ind in cur_inds:
            delta: float | None = None
            if prior is not None and ind.value is not None:
                prior_val = (
                    session.query(PanelIndicator.value)
                    .filter_by(feed_id=prior.feed_id, indicator_id=ind.indicator_id)
                    .scalar()
                )
                if prior_val is not None and float(prior_val) != 0:
                    delta = (
                        (float(ind.value) - float(prior_val))
                        / float(prior_val)
                        * 100.0
                    )

            _upsert_derived(
                session,
                post.feed_id,
                ind.indicator_id,
                methodology_commit=methodology_commit,
                post_reorg_delta_pct=delta,
            )
            n_updated += 1

    session.commit()
    return n_updated
