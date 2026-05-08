"""Spec §5.1 E. Frequency & speed indicators (4 items). Plan 2 Task 3.2.

Indicators:
    - freq_peak_headway_median   (minutes) median of per-route median peak headway
    - freq_high_freq_lines_pct   (%)       % of routes with median peak headway <= 10 min
    - freq_daily_service_hours   (hours)   network amplitude (max arr - min dep)
    - freq_commercial_speed_kmh  (km/h)    Sigma trip_dist / Sigma trip_duration

Public helper:
    _peak_headway_per_route(raw, normed) -> dict[int, float | None]
        Also imported by coverage.compute_all (Task 3.3) to identify high-frequency
        stops for cov_pop_freq_300m. Plan 2 Assumption A7: a route is "high-frequency"
        iff its median peak headway <= 10 min.
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np
import pandas as pd


# Hour buckets: same as structure.py's peak hours (4-hour balanced cross-AOM benchmark).
PEAK_HOURS: frozenset[int] = frozenset({7, 8, 17, 18})

# Plan 2 Assumption A7: a route is "high-frequency" iff its median peak headway <= 10 min.
HIGH_FREQ_HEADWAY_MIN: float = 10.0


def compute_all(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> dict[str, float | None]:
    """Compute all 4 frequency & speed indicators (Spec §5.1 E).

    Args:
        raw: Output of `read_gtfs_zip` (raw GTFS dict-of-DataFrames).
        normed: Output of `gtfs_normalize`.

    Returns:
        {indicator_id: value}. None where computation impossible (empty
        trips, missing tables, no peak service, etc.).
    """
    out: dict[str, float | None] = {}

    headways = _peak_headway_per_route(raw, normed)
    valid = [h for h in headways.values() if h is not None]
    if valid:
        out["freq_peak_headway_median"] = float(pd.Series(valid).median())
        out["freq_high_freq_lines_pct"] = (
            100.0 * sum(1 for h in valid if h <= HIGH_FREQ_HEADWAY_MIN) / len(valid)
        )
    else:
        out["freq_peak_headway_median"] = None
        out["freq_high_freq_lines_pct"] = None

    out["freq_daily_service_hours"] = _daily_service_hours(raw, normed)
    out["freq_commercial_speed_kmh"] = _commercial_speed_kmh(raw, normed)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Public helper — also imported by coverage.compute_all (Task 3.3)
# ──────────────────────────────────────────────────────────────────────────────


def _peak_headway_per_route(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> dict[int, float | None]:
    """Median peak headway (minutes) per route_id (id_ligne_num).

    Used by:
      1. frequency.compute_all (this module) for freq_peak_headway_median
         + freq_high_freq_lines_pct
      2. coverage.compute_all (Task 3.3) to identify high-frequency stops for
         cov_pop_freq_300m.

    Algorithm:
        - For each trip, take the first stop's departure_time as the trip start.
        - Bucket by hour-of-day, modulo 24 to absorb after-midnight services
          (GTFS allows 25:30:00 etc).
        - Filter to peak hours {7, 8, 17, 18}.
        - Per (route, peak_hour): headway = 60 min / trip_count.
        - Per route: return the median across the available peak hours.

    Returns:
        {id_ligne_num: median_peak_headway_min}. Routes with no peak service
        get None. Empty dict if upstream tables are missing or malformed.

    Note:
        Despite the underscore prefix, this is a public helper. Python does
        not enforce visibility; the underscore reflects internal-helper
        convention but Task 3.3 imports it intentionally.
    """
    stop_times = normed.get("stop_times")
    trips = normed.get("trips")
    if stop_times is None or trips is None or len(stop_times) == 0 or len(trips) == 0:
        return {}
    if "id_course_num" not in stop_times.columns or "id_course_num" not in trips.columns:
        return {}
    if "id_ligne_num" not in trips.columns:
        return {}
    if "departure_time" not in stop_times.columns or "stop_sequence" not in stop_times.columns:
        return {}

    # First stop_time per trip = the trip's departure time.
    st_first = (
        stop_times.sort_values(["id_course_num", "stop_sequence"])
        .groupby("id_course_num", as_index=False)
        .first()
    )

    # Parse leading HH segment of HH:MM:SS, mod 24 to absorb after-midnight times.
    hh = pd.to_numeric(
        st_first["departure_time"].astype(str).str.split(":", n=1).str[0],
        errors="coerce",
    )
    valid_mask = hh.notna()
    st_first = st_first.loc[valid_mask].copy()
    if len(st_first) == 0:
        # No valid departure times -> all routes report None.
        all_routes = trips["id_ligne_num"].dropna().unique()
        return {int(rid): None for rid in all_routes}
    st_first["_hour"] = hh.loc[valid_mask].astype(int) % 24

    # Join trip -> route.
    merged = st_first[["id_course_num", "_hour"]].merge(
        trips[["id_course_num", "id_ligne_num"]], on="id_course_num", how="left"
    )
    merged = merged.dropna(subset=["id_ligne_num"])

    # Initialise result with all known routes -> None, then overwrite where peak service exists.
    all_routes = trips["id_ligne_num"].dropna().unique()
    result: dict[int, float | None] = {int(rid): None for rid in all_routes}

    peak = merged[merged["_hour"].isin(PEAK_HOURS)]
    if len(peak) == 0:
        return result

    # Per (route, peak_hour) -> trip count -> headway = 60 / count
    counts = peak.groupby(["id_ligne_num", "_hour"]).size().reset_index(name="trips")
    counts["headway_min"] = 60.0 / counts["trips"].astype(float)
    per_route = counts.groupby("id_ligne_num")["headway_min"].median()

    for rid, val in per_route.items():
        result[int(rid)] = float(val)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────


def _daily_service_hours(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> float | None:
    """Spec §5.1 E: network service-hours amplitude.

    Algorithm:
        max(arrival_time) - min(departure_time) across all stop_times,
        in hours. Departure / arrival values may exceed 24h (GTFS extended
        hours such as 25:30:00); we keep the raw hours so the diff is in
        wall-clock hours of operation.

    Spec lists this separately from prod_service_amplitude to surface the
    "frequency lens" view (Plan 2 Assumption A10 -- per-date averaging is
    handled in productivity; here we expose the network-wide span).

    Returns None if stop_times missing or times unparseable.
    """
    stop_times = normed.get("stop_times")
    if stop_times is None or len(stop_times) == 0:
        return None
    if "departure_time" not in stop_times.columns or "arrival_time" not in stop_times.columns:
        return None

    dep = _to_hours(stop_times["departure_time"])
    arr = _to_hours(stop_times["arrival_time"])
    dep_min = dep.min()
    arr_max = arr.max()
    if pd.isna(dep_min) or pd.isna(arr_max):
        return None
    amplitude = float(arr_max - dep_min)
    return amplitude if amplitude > 0 else None


def _commercial_speed_kmh(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
) -> float | None:
    """Spec §5.1 E: Sigma trip_distance_km / Sigma trip_duration_h.

    - Trip distance: cumulative Haversine across consecutive stops within
      a course (id_course_num).
    - Trip duration: last_stop.arrival_time - first_stop.departure_time.

    Aggregated across ALL trips (not per-route averaged) -- matches the
    GART convention for commercial speed.

    Returns None if upstream tables missing, no valid trips, or
    aggregate duration is non-positive.
    """
    stop_times = normed.get("stop_times")
    stops = normed.get("stops")
    if stop_times is None or stops is None or len(stop_times) == 0 or len(stops) == 0:
        return None
    if "id_course_num" not in stop_times.columns or "stop_sequence" not in stop_times.columns:
        return None
    if "departure_time" not in stop_times.columns or "arrival_time" not in stop_times.columns:
        return None
    if "stop_id" not in stop_times.columns or "stop_id" not in stops.columns:
        return None
    if "stop_lat" not in stops.columns or "stop_lon" not in stops.columns:
        return None

    st = stop_times.sort_values(["id_course_num", "stop_sequence"]).copy()
    st = st.merge(stops[["stop_id", "stop_lat", "stop_lon"]], on="stop_id", how="left")
    st = st.dropna(subset=["stop_lat", "stop_lon"])
    if len(st) == 0:
        return None

    # Per-trip cumulative Haversine (vectorised: shift within course group).
    st["_lat_prev"] = st.groupby("id_course_num")["stop_lat"].shift(1)
    st["_lon_prev"] = st.groupby("id_course_num")["stop_lon"].shift(1)
    pair = st.dropna(subset=["_lat_prev", "_lon_prev"])
    if len(pair) == 0:
        return None

    R = 6_371_000.0
    lat1 = np.radians(pair["_lat_prev"].astype(float).to_numpy())
    lat2 = np.radians(pair["stop_lat"].astype(float).to_numpy())
    dlat = np.radians(
        (pair["stop_lat"].astype(float) - pair["_lat_prev"].astype(float)).to_numpy()
    )
    dlon = np.radians(
        (pair["stop_lon"].astype(float) - pair["_lon_prev"].astype(float)).to_numpy()
    )
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    dist_m = 2 * R * np.arcsin(np.sqrt(a))
    total_dist_km = float(dist_m.sum()) / 1000.0
    if total_dist_km <= 0.0:
        return None

    # Per-trip duration: last_arr - first_dep (in hours), summed.
    st["_dep_h"] = _to_hours(st["departure_time"])
    st["_arr_h"] = _to_hours(st["arrival_time"])
    per_trip = st.groupby("id_course_num").agg(
        _start=("_dep_h", "min"), _end=("_arr_h", "max")
    )
    durations = per_trip["_end"] - per_trip["_start"]
    total_dur_h = float(durations[durations > 0].sum())
    if total_dur_h <= 0.0:
        return None

    return total_dist_km / total_dur_h


# ──────────────────────────────────────────────────────────────────────────────
# Time parsing utility
# ──────────────────────────────────────────────────────────────────────────────


def _to_hours(s: pd.Series) -> pd.Series:
    """Parse HH:MM:SS strings (GTFS extended hours allowed) into float hours.

    Returns NaN for unparseable rows. Does NOT take modulo 24 -- callers
    that need wall-clock buckets (e.g., peak hour filtering) should
    apply % 24 themselves.
    """
    parts = s.astype(str).str.split(":", expand=True)
    h = pd.to_numeric(parts[0], errors="coerce")
    m = pd.to_numeric(parts[1], errors="coerce") if parts.shape[1] >= 2 else 0.0
    sec = pd.to_numeric(parts[2], errors="coerce") if parts.shape[1] >= 3 else 0.0
    return h + m / 60.0 + sec / 3600.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two (lat, lon) points.

    Currently only used internally; exposed for symmetry with structure.py
    and possible reuse by coverage in Task 3.3.
    """
    R = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
