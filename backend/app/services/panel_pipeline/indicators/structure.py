"""Spec §5.1 C. Network structure indicators (7 items).

Task 2.5 implements modal mix (4). Task 2.6 implements peak amplification,
multi-route stops %, and route directness (3).
"""
from __future__ import annotations

import math
from typing import Mapping

import pandas as pd


# GTFS route_type values per spec §5.1 C
_ROUTE_TYPE_BUS = 3
_ROUTE_TYPE_TRAM = 0
_ROUTE_TYPE_METRO = 1
_ROUTE_TYPE_TRAIN = 2

# Hour buckets for peak amplification (4 hours each, balanced cross-AOM benchmark).
# Mid-morning + mid-afternoon avoids both AM/PM rush AND late-night service tail-off.
_PEAK_HOURS = frozenset({7, 8, 17, 18})
_OFFPEAK_HOURS = frozenset({10, 11, 14, 15})


def compute_all(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> dict[str, float | None]:
    """Compute structure indicators (Phase 2 Tasks 2.5 + 2.6).

    Args:
        raw: Output of `read_gtfs_zip` (dict-of-DataFrames, raw GTFS).
        normed: Output of `gtfs_normalize`.

    Returns:
        {indicator_id: value}. Modal-mix percentages in [0, 100] -- never None
        (a 0% result is meaningful, not missing). Advanced indicators may be
        None if upstream tables are missing or malformed.
    """
    out: dict[str, float | None] = {}
    out.update(_modal_mix(raw, normed))
    out["struct_peak_amplification"]    = _peak_amplification(raw, normed)
    out["struct_multi_route_stops_pct"] = _multi_route_stops_pct(raw, normed)
    out["struct_route_directness"]      = _route_directness(raw, normed)
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


# ──────────────────────────────────────────────────────────────────────────────
# Task 2.6 helpers
# ──────────────────────────────────────────────────────────────────────────────


def _peak_amplification(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> float | None:
    """Spec §5.1 C: peak hour trips / off-peak hour trips.

    Algorithm:
        - For each trip, derive hour-of-day from first stop's departure_time
          (parsing the HH segment of HH:MM:SS, modulo 24 to handle GTFS
          after-midnight values like 25:30:00).
        - Bucket: peak in {7, 8, 17, 18}; off-peak in {10, 11, 14, 15}
          (4 hours each, balanced).
        - Both buckets are 4-hour wide -> ratio of total trip counts equals
          ratio of mean trips/hour. Return that ratio directly.

    Note: a balanced 4x4 hour comparison is the cleanest cross-AOM benchmark.
    Spec is loose on which hours count as off-peak; mid-morning + mid-afternoon
    avoids both AM/PM rush AND late-night service tail-off.

    Returns None if either bucket has zero trips, or required tables missing.
    """
    stop_times = normed.get("stop_times")
    trips = normed.get("trips")
    if stop_times is None or trips is None or len(stop_times) == 0 or len(trips) == 0:
        return None
    # In normed-land, stop_times has 'id_course_num' replacing 'trip_id' (gtfs_norm:270).
    if "id_course_num" not in stop_times.columns or "departure_time" not in stop_times.columns:
        return None

    # First stop_time of each trip = the trip's departure time
    st_sorted = stop_times.sort_values(["id_course_num", "stop_sequence"])
    first_st = st_sorted.groupby("id_course_num", as_index=False).first()

    # departure_time is the original HH:MM:SS string (post-norm but pre-generator).
    # Parse the leading HH segment, mod 24 to handle GTFS extended hours (25:30:00).
    dep = first_st["departure_time"].astype(str)
    hh = pd.to_numeric(dep.str.split(":", n=1).str[0], errors="coerce")
    hh = hh.dropna().astype(int) % 24
    if len(hh) == 0:
        return None

    peak_count = int(hh.isin(_PEAK_HOURS).sum())
    offpeak_count = int(hh.isin(_OFFPEAK_HOURS).sum())
    if offpeak_count == 0:
        return None
    return float(peak_count) / float(offpeak_count)


def _multi_route_stops_pct(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> float | None:
    """Spec §5.1 C: % of stops served by >=2 routes.

    Algorithm:
        - Build (stop_id, route) edge set from stop_times -> trips.
        - Count distinct routes per stop.
        - Return: 100 * (stops with >=2 routes) / (total stops served).
    """
    stop_times = normed.get("stop_times")
    trips = normed.get("trips")
    if stop_times is None or trips is None or len(stop_times) == 0 or len(trips) == 0:
        return None
    # In normed-land: stop_times.id_course_num + trips.[id_course_num, id_ligne_num].
    if ("id_course_num" not in stop_times.columns
            or "id_course_num" not in trips.columns
            or "id_ligne_num" not in trips.columns):
        return None

    edges = (
        stop_times[["stop_id", "id_course_num"]]
        .merge(trips[["id_course_num", "id_ligne_num"]], on="id_course_num")
        [["stop_id", "id_ligne_num"]]
        .drop_duplicates()
    )
    if len(edges) == 0:
        return None
    routes_per_stop = edges.groupby("stop_id").size()
    total = int(len(routes_per_stop))
    if total == 0:
        return None
    multi = int((routes_per_stop >= 2).sum())
    return 100.0 * multi / total


def _route_directness(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> float | None:
    """Spec §5.1 C + Plan 2 Assumption A8: shape-free directness.

    Per route, take ONE representative trip (longest by stop count). Compute:
        - Cumulative Haversine across consecutive stop pairs (actual path)
        - Origin -> terminus great-circle (straight line)
        - Ratio = actual / great_circle (>=1.0; closer to 1 = more direct)
    Return median across routes. Loop routes (gc=0) are skipped (undefined).

    Returns None if no routes have >=2 stops, or required tables missing.
    """
    stop_times = normed.get("stop_times")
    stops = normed.get("stops")
    trips = normed.get("trips")
    if stop_times is None or stops is None or trips is None:
        return None
    if len(stop_times) == 0 or len(stops) == 0 or len(trips) == 0:
        return None
    if ("id_course_num" not in stop_times.columns
            or "id_ligne_num" not in trips.columns
            or "id_course_num" not in trips.columns):
        return None

    # 1. For each route, pick the trip with the most stops.
    st_counts = stop_times.groupby("id_course_num").size().reset_index(name="n_stops")
    st_counts = st_counts.merge(trips[["id_course_num", "id_ligne_num"]], on="id_course_num")
    longest_per_route = (
        st_counts
        .sort_values(["id_ligne_num", "n_stops"], ascending=[True, False])
        .drop_duplicates("id_ligne_num", keep="first")[["id_ligne_num", "id_course_num"]]
    )
    if len(longest_per_route) == 0:
        return None

    # 2. For each chosen trip, build the stop sequence with lat/lon and compute ratio.
    stops_lookup = stops.set_index("stop_id")[["stop_lat", "stop_lon"]]
    chosen_courses = set(longest_per_route["id_course_num"].tolist())
    # Pre-filter stop_times once for performance on bigger feeds.
    st_subset = stop_times[stop_times["id_course_num"].isin(chosen_courses)].copy()
    st_subset = st_subset.sort_values(["id_course_num", "stop_sequence"])
    st_subset = st_subset.merge(stops_lookup, on="stop_id", how="left")
    st_subset = st_subset.dropna(subset=["stop_lat", "stop_lon"])

    ratios: list[float] = []
    for _, group in st_subset.groupby("id_course_num", sort=False):
        if len(group) < 2:
            continue
        lats = group["stop_lat"].to_numpy()
        lons = group["stop_lon"].to_numpy()
        # Cumulative Haversine across consecutive stop pairs.
        actual = 0.0
        for i in range(len(group) - 1):
            actual += _haversine_m(lats[i], lons[i], lats[i + 1], lons[i + 1])
        # Origin -> terminus.
        gc = _haversine_m(lats[0], lons[0], lats[-1], lons[-1])
        if gc <= 0.0:
            continue  # Loop route -- undefined directness.
        ratios.append(actual / gc)

    if not ratios:
        return None
    return float(pd.Series(ratios).median())


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two (lat, lon) points."""
    R = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
