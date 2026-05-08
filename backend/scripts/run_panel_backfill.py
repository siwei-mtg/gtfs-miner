"""PAN full backfill driver — Plan 2 Task 7.3 (spec §6.4).

Enumerates feeds whose ``process_status`` is ``pending`` or ``failed`` and
enqueues a ``panel.run`` Celery task for each. When Celery is unavailable
(e.g. dev / smoke runs without Redis) the script falls back to inline
``run_panel_pipeline()`` execution.

Usage:
    python run_panel_backfill.py [--limit N] [--dry-run]

Estimated runtime (without ``--dry-run``):
    463 networks x ~65 feeds/network x ~30s/feed / 4 workers ~ 63h on
    a 4-core machine. Practical operation: split the queue across
    multiple Celery workers (Windows: -P solo) and resume failed feeds
    by re-running with ``--limit`` or filtering on ``process_status``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import PanelFeed  # noqa: E402

INVENTORY_CSV = (
    Path(__file__).resolve().parents[1]
    / "storage"
    / "discovery"
    / "d1_pan"
    / "datasets_gtfs_inventory.csv"
)


def enumerate_pending_feeds(session, limit: int | None = None) -> list[str]:
    """Return ``feed_id``s whose ``process_status`` is ``pending`` / ``failed``
    / NULL, oldest ``feed_start_date`` first.

    Args:
        session: an active SQLAlchemy session.
        limit:  if given, cap the result to the first N rows.
    """
    q = (
        session.query(PanelFeed.feed_id)
        .filter(PanelFeed.process_status.in_(["pending", "failed", None]))
        .order_by(PanelFeed.feed_start_date.asc())
    )
    if limit:
        q = q.limit(limit)
    return [row[0] for row in q]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, help="Process only the first N feeds")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="List feeds that would be enqueued without dispatching",
    )
    args = p.parse_args(argv)

    with SessionLocal() as s:
        feed_ids = enumerate_pending_feeds(s, limit=args.limit)

    print(f"Found {len(feed_ids)} feed(s) to process")
    if args.dry_run:
        for fid in feed_ids[:20]:
            print(f"  would enqueue: {fid}")
        if len(feed_ids) > 20:
            print(f"  ... and {len(feed_ids) - 20} more")
        return

    # Enqueue via Celery; fall back to inline execution when broker missing.
    try:
        from app.services.worker import panel_run_task

        for fid in feed_ids:
            panel_run_task.delay(fid)
        print(f"Enqueued {len(feed_ids)} task(s)")
    except ImportError as e:
        print(f"WARN: Celery not available ({e}); falling back to inline run")
        from app.services.panel_pipeline.run import run_panel_pipeline

        for fid in feed_ids:
            try:
                run_panel_pipeline(fid)
            except Exception as exc:  # noqa: BLE001 — driver swallows per-feed errors
                print(f"  failed feed_id={fid}: {exc}")


if __name__ == "__main__":
    main()
