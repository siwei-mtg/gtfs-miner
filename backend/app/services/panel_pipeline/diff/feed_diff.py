"""Feed-pair diff: added/removed/modified for stops and routes. Pure function.

Input schema (per side, ``a`` and ``b`` are ``Mapping[str, pd.DataFrame]``):
    stops: DataFrame[stop_id, stop_name, stop_lat, stop_lon, ...]
    routes: DataFrame[route_id, route_short_name, route_type, ...]

Output schema:
    FeedDiff dataclass with:
        stops_added / stops_removed: sorted list[str] of stop_id
        stops_modified: dict[stop_id, dict[field_name, [old, new]]]
        routes_added / routes_removed: sorted list[str] of route_id
        routes_modified: dict[route_id, dict[field_name, [old, new]]]
        stop_jaccard / route_jaccard: float in [0.0, 1.0]
            (1.0 when both sets are empty)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd


STOP_TRACKED_FIELDS = ("stop_name", "stop_lat", "stop_lon", "location_type")
ROUTE_TRACKED_FIELDS = ("route_short_name", "route_long_name", "route_type")


@dataclass(frozen=True, slots=True)
class FeedDiff:
    stops_added: list[str]
    stops_removed: list[str]
    stops_modified: dict[str, dict[str, list]]
    routes_added: list[str]
    routes_removed: list[str]
    routes_modified: dict[str, dict[str, list]]
    stop_jaccard: float
    route_jaccard: float


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _ne(x: object, y: object) -> bool:
    """Compare two scalars, treating NaN-on-both-sides as equal."""
    if pd.isna(x) and pd.isna(y):
        return False
    return x != y


def _diff_records(
    a: pd.DataFrame, b: pd.DataFrame, key: str, tracked: Sequence[str],
) -> tuple[list[str], list[str], dict[str, dict[str, list]]]:
    if a[key].duplicated().any():
        dup_ids = a.loc[a[key].duplicated(), key].astype(str).head().tolist()
        raise ValueError(f"duplicate {key} in feed a: {dup_ids}")
    if b[key].duplicated().any():
        dup_ids = b.loc[b[key].duplicated(), key].astype(str).head().tolist()
        raise ValueError(f"duplicate {key} in feed b: {dup_ids}")
    a_ids = set(a[key].astype(str))
    b_ids = set(b[key].astype(str))
    added = sorted(b_ids - a_ids)
    removed = sorted(a_ids - b_ids)
    modified: dict[str, dict[str, list]] = {}
    common = a_ids & b_ids
    if common:
        a_idx = a.set_index(a[key].astype(str))
        b_idx = b.set_index(b[key].astype(str))
        for cid in sorted(common):
            ra, rb = a_idx.loc[cid], b_idx.loc[cid]
            field_diffs = {
                f: [ra.get(f), rb.get(f)]
                for f in tracked
                if f in a.columns and f in b.columns and _ne(ra.get(f), rb.get(f))
            }
            if field_diffs:
                modified[cid] = field_diffs
    return added, removed, modified


def feed_diff(a: Mapping[str, pd.DataFrame], b: Mapping[str, pd.DataFrame]) -> FeedDiff:
    """Diff two GTFS feeds (raw dict-of-DataFrames from ``read_gtfs_zip``).

    Input schema:
        a, b: Mapping with keys "stops" and "routes":
            stops: DataFrame[stop_id, stop_name, stop_lat, stop_lon, ...]
            routes: DataFrame[route_id, route_short_name, route_type, ...]

    Output schema:
        FeedDiff (see module docstring).
    """
    s_added, s_removed, s_modified = _diff_records(
        a["stops"], b["stops"], key="stop_id", tracked=STOP_TRACKED_FIELDS,
    )
    r_added, r_removed, r_modified = _diff_records(
        a["routes"], b["routes"], key="route_id", tracked=ROUTE_TRACKED_FIELDS,
    )
    return FeedDiff(
        stops_added=s_added, stops_removed=s_removed, stops_modified=s_modified,
        routes_added=r_added, routes_removed=r_removed, routes_modified=r_modified,
        stop_jaccard=_jaccard(set(a["stops"]["stop_id"].astype(str)),
                              set(b["stops"]["stop_id"].astype(str))),
        route_jaccard=_jaccard(set(a["routes"]["route_id"].astype(str)),
                               set(b["routes"]["route_id"].astype(str))),
    )
