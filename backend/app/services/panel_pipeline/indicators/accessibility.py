"""Spec §5.1 F. Accessibility indicators (2 items).

Reads directly from raw GTFS dict (read_gtfs_zip output). gtfs_normalize
strips wheelchair_boarding from stops_norm output (only the hardcoded
`essentials` subset survives), and trips_norm does not guarantee
wheelchair_accessible is preserved either -- using `raw` avoids touching
the worker pipeline contract and the KCC bit-equivalence.
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd


def compute_all(
    raw: Mapping[str, pd.DataFrame],
) -> dict[str, float | None]:
    """Compute the 2 accessibility indicators.

    Per GTFS spec, wheelchair_boarding and wheelchair_accessible use:
        1 -> wheelchair accessible
        2 -> explicitly NOT accessible
        0 or null -> no information

    The indicator counts only =1 as accessible.

    Args:
        raw: Output of `read_gtfs_zip`. Must contain `stops` and `trips`.

    Returns:
        {indicator_id: value}. None if source column absent; 0.0 if column
        present but no stops/trips have value=1.
    """
    return {
        "acc_wheelchair_stops_pct": _wheelchair_stops_pct(raw),
        "acc_wheelchair_trips_pct": _wheelchair_trips_pct(raw),
    }


def _wheelchair_stops_pct(raw: Mapping[str, pd.DataFrame]) -> float | None:
    stops = raw.get("stops")
    if stops is None or len(stops) == 0:
        return None
    if "wheelchair_boarding" not in stops.columns:
        return None
    # Filter to physical stops (location_type=0 or absent), same convention
    # as prod_stops_count.
    if "location_type" in stops.columns:
        physical = stops[
            pd.to_numeric(stops["location_type"], errors="coerce").fillna(0).astype(int) == 0
        ]
    else:
        physical = stops
    if len(physical) == 0:
        return None
    flags = pd.to_numeric(physical["wheelchair_boarding"], errors="coerce").fillna(0)
    accessible = int((flags.astype(int) == 1).sum())
    return float(accessible) / len(physical) * 100.0


def _wheelchair_trips_pct(raw: Mapping[str, pd.DataFrame]) -> float | None:
    trips = raw.get("trips")
    if trips is None or len(trips) == 0:
        return None
    if "wheelchair_accessible" not in trips.columns:
        return None
    flags = pd.to_numeric(trips["wheelchair_accessible"], errors="coerce").fillna(0)
    accessible = int((flags.astype(int) == 1).sum())
    return float(accessible) / len(trips) * 100.0
