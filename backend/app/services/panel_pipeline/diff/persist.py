"""Persist FeedDiff + ReorgVerdict to panel_feed_diffs / panel_reorg_flags.

Idempotent on:
    - (feed_from_id, feed_to_id) for panel_feed_diffs (UNIQUE constraint enforces this at DB level too)
    - (network_id, feed_to_id) for panel_reorg_flags (composite PK)

Spec §6.3.2 v0.2.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import PanelFeedDiff, PanelReorgFlag
from app.services.panel_pipeline.diff.feed_diff import FeedDiff
from app.services.panel_pipeline.diff.reorg_detect import ReorgVerdict


def persist_diff_and_flag(
    session: Session,
    network_id: str,
    feed_from_id: str,
    feed_to_id: str,
    diff: FeedDiff,
    verdict: ReorgVerdict,
) -> None:
    """Idempotently write the diff + verdict for one (feed_from, feed_to) pair.

    Re-running with the same inputs is a no-op (existing rows kept). The reorg
    flag is written even when verdict.detected is False — downstream aggregator
    uses the absence of a flag row to detect "not yet computed", separately from
    "computed and confirmed not a reorg".

    Args:
        session: SQLAlchemy session — caller controls transaction boundary.
        network_id: panel_networks.network_id (FK on both tables).
        feed_from_id: earlier feed (t).
        feed_to_id: later feed (t+1).
        diff: FeedDiff produced by feed_diff().
        verdict: ReorgVerdict produced by detect_reorg().
    """
    existing_diff = (
        session.query(PanelFeedDiff)
        .filter_by(feed_from_id=feed_from_id, feed_to_id=feed_to_id)
        .one_or_none()
    )
    if existing_diff is None:
        session.add(PanelFeedDiff(
            network_id=network_id,
            feed_from_id=feed_from_id, feed_to_id=feed_to_id,
            stops_added=diff.stops_added, stops_removed=diff.stops_removed,
            stops_modified=diff.stops_modified,
            routes_added=diff.routes_added, routes_removed=diff.routes_removed,
            routes_modified=diff.routes_modified,
            stop_jaccard=diff.stop_jaccard, route_jaccard=diff.route_jaccard,
        ))

    existing_flag = (
        session.query(PanelReorgFlag)
        .filter_by(network_id=network_id, feed_to_id=feed_to_id)
        .one_or_none()
    )
    if existing_flag is None:
        session.add(PanelReorgFlag(
            network_id=network_id, feed_to_id=feed_to_id,
            reorg_detected=verdict.detected, reorg_severity=verdict.severity,
            stop_jaccard=verdict.stop_jaccard, route_jaccard=verdict.route_jaccard,
            threshold_version=verdict.threshold_version,
        ))
    session.commit()
