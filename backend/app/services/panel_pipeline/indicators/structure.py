"""Spec §5.1 C. Network structure indicators (7 items).

Task 2.5 implements modal mix (4). Task 2.6 implements peak amplification,
multi-route stops %, and route directness (3).
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd


# GTFS route_type values per spec §5.1 C
_ROUTE_TYPE_BUS = 3
_ROUTE_TYPE_TRAM = 0
_ROUTE_TYPE_METRO = 1
_ROUTE_TYPE_TRAIN = 2


def compute_all(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> dict[str, float | None]:
    """Compute structure indicators (Phase 2 Task 2.5: modal mix only).

    Args:
        raw: Output of `read_gtfs_zip` (dict-of-DataFrames, raw GTFS).
        normed: Output of `gtfs_normalize`.

    Returns:
        {indicator_id: value}. Modal-mix percentages in [0, 100] -- never None
        (a 0% result is meaningful, not missing).
    """
    out: dict[str, float | None] = {}
    out.update(_modal_mix(raw, normed))
    # Phase 2 Task 2.6 fills the remaining 3 structure indicators
    return out


def _modal_mix(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> dict[str, float]:
    """Spec §5.1 C: % of trips by route_type.

    Joins normed["trips"] to normed["routes"] on route_id (or id_ligne_num if
    routes is already keyed by it). Counts trips per route_type, divides by
    total trips x 100. Returns 0.0 for absent modes.

    Note: bus/tram/metro/train cover dominant urban modes; ferry/cable/etc.
    are not surfaced as separate indicators per spec §5.1 C, so the 4 values
    may sum to <100% for multi-modal networks.
    """
    routes = normed["routes"]
    trips = normed["trips"]
    if len(trips) == 0 or len(routes) == 0:
        return {
            "struct_modal_mix_bus": 0.0,
            "struct_modal_mix_tram": 0.0,
            "struct_modal_mix_metro": 0.0,
            "struct_modal_mix_train": 0.0,
        }

    # gtfs_norm replaces route_id with id_ligne_num in trips and adds id_ligne_num to routes.
    # Use that as the join key. Otherwise fall back to route_id.
    if "id_ligne_num" in trips.columns and "id_ligne_num" in routes.columns:
        join_key = "id_ligne_num"
    elif "route_id" in trips.columns and "route_id" in routes.columns:
        join_key = "route_id"
    else:
        return {
            "struct_modal_mix_bus": 0.0,
            "struct_modal_mix_tram": 0.0,
            "struct_modal_mix_metro": 0.0,
            "struct_modal_mix_train": 0.0,
        }

    rt = routes[[join_key, "route_type"]].drop_duplicates()
    merged = trips[[join_key]].merge(rt, on=join_key, how="left")
    total = len(merged)
    if total == 0:
        return {
            "struct_modal_mix_bus": 0.0,
            "struct_modal_mix_tram": 0.0,
            "struct_modal_mix_metro": 0.0,
            "struct_modal_mix_train": 0.0,
        }
    counts = merged["route_type"].value_counts()
    pct = lambda code: float(counts.get(code, 0)) / total * 100.0
    return {
        "struct_modal_mix_bus":   pct(_ROUTE_TYPE_BUS),
        "struct_modal_mix_tram":  pct(_ROUTE_TYPE_TRAM),
        "struct_modal_mix_metro": pct(_ROUTE_TYPE_METRO),
        "struct_modal_mix_train": pct(_ROUTE_TYPE_TRAIN),
    }
