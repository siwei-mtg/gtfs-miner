"""Idempotent loader: methodology/data/dsp_timeline.csv -> panel_dsp_events.

Spec section 22 + Plan 2 Assumption A2:
    Row hash includes ``notes`` and ``boamp_url``. Contributor edits insert new
    rows, preserving audit trail. UI reads latest by (network, type, date).

Usage::

    python load_dsp_events.py [path/to/dsp_timeline.csv]

If no path given, defaults to ``../compare-transit-methodology/data/dsp_timeline.csv``
relative to the GTFS Miner repo root.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Make ``app.*`` importable when this file is run as a script
# (consistent with discovery/d2_insee_coverage.py / d6_reorg_thresholds.py).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import PanelDspEvent, PanelNetwork  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


HASH_FIELDS: tuple[str, ...] = (
    "network_slug",
    "event_type",
    "event_date",
    "operator_before",
    "operator_after",
    "source",
    "boamp_url",
    "notes",
)


def compute_row_hash(row: dict) -> str:
    """SHA-256 over the canonical pipe-joined business fields. Plan 2 Assumption A2.

    Including ``notes`` means contributor edits to that field generate a new
    hash, so the loader inserts a new row (audit trail) instead of overwriting.
    """
    payload = "|".join(str(row.get(f, "")) for f in HASH_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_dsp_events(session: Session, csv_path: Path) -> int:
    """Load ``dsp_timeline.csv`` into ``panel_dsp_events``.

    Args:
        session: SQLAlchemy session - caller controls transaction. This function
            commits at the end.
        csv_path: Path to dsp_timeline.csv (UTF-8, comma-separated header row).

    Returns:
        Number of rows newly inserted (0 means everything was already present
        or all rows referenced unknown networks).

    Input schema (CSV columns):
        network_slug, event_type, event_date (ISO YYYY-MM-DD), operator_before,
        operator_after, contract_id, contract_value_eur, boamp_url, notes,
        source, contributor.

    Output: writes rows to ``panel_dsp_events`` (one row per unique
    ``csv_row_hash``). Unknown ``network_slug`` -> warn + skip. Unparseable
    ``event_date`` -> warn + skip.
    """
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    if df.empty:
        return 0

    slugs = set(df["network_slug"].unique())
    networks: dict[str, str] = {
        n.slug: n.network_id
        for n in session.query(PanelNetwork).filter(PanelNetwork.slug.in_(slugs))
    }

    inserted = 0
    for _, r in df.iterrows():
        slug = r["network_slug"]
        if slug not in networks:
            print(f"WARN: skipping unknown network_slug={slug}", file=sys.stderr)
            continue
        h = compute_row_hash(r.to_dict())
        if session.query(PanelDspEvent).filter_by(csv_row_hash=h).first():
            continue
        try:
            event_date = datetime.fromisoformat(r["event_date"])
        except (ValueError, TypeError):
            print(
                f"WARN: skipping row with unparseable event_date={r['event_date']!r}",
                file=sys.stderr,
            )
            continue
        contract_value = (
            float(r["contract_value_eur"]) if r["contract_value_eur"] else None
        )
        session.add(PanelDspEvent(
            network_id=networks[slug],
            event_type=r["event_type"],
            event_date=event_date,
            operator_before=r["operator_before"] or None,
            operator_after=r["operator_after"] or None,
            contract_id=r["contract_id"] or None,
            contract_value_eur=contract_value,
            boamp_url=r["boamp_url"] or None,
            notes=r["notes"] or None,
            source=r["source"],
            contributor=r["contributor"],
            csv_row_hash=h,
        ))
        inserted += 1

    session.commit()
    return inserted


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Load dsp_timeline.csv into panel_dsp_events."
    )
    default_csv = (
        Path(__file__).resolve().parents[2]
        / "compare-transit-methodology" / "data" / "dsp_timeline.csv"
    )
    p.add_argument(
        "csv", nargs="?", type=Path, default=default_csv,
        help=f"Path to dsp_timeline.csv (default: {default_csv})",
    )
    args = p.parse_args(argv)

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    with SessionLocal() as s:
        n = load_dsp_events(s, args.csv)
        print(f"Loaded {n} new DSP event(s) from {args.csv}")


if __name__ == "__main__":
    main()
