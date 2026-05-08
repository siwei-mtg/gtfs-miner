"""Spec §5.1 A. Productivity indicators (8 items).

Phase 2 Task 2.1 implemented 3 of 8:
    prod_kcc_year, prod_lines_count, prod_stops_count.

Phase 2 Task 2.2 added 3 more:
    prod_courses_day_avg, prod_peak_hour_courses, prod_service_amplitude.

Phase 2 Task 2.3 fills the remaining 2 (this file):
    prod_network_length_km, prod_peak_vehicles_needed.

Implementation note (Task 2.2 refactor): the chain that produces the KCC pivot
(`AP, AG, lignes, courses, courses_export, lignes_export, sjt, service_dates`)
is reused by the new count indicators. To avoid running it 3-4× per
`compute_all` call, it has been extracted into `_compute_chain` and the
intermediates packaged in a frozen `_Chain` dataclass. `_kcc_year` is now a
thin pivot-summation over `chain`; the new indicator helpers take `chain`
plus `normed` (for `stop_times` access where needed) and produce floats.

Task 2.3 extends `_Chain` with `itineraire_arc` so the network-length
indicator can dedupe undirected geographic segments without recomputing
Haversine distances (already populated in `itineraire_arc.DIST_Vol_Oiseau`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import pandas as pd


# ──────────────────────────────────────────────────────────────────────────────
# Public entrypoint
# ──────────────────────────────────────────────────────────────────────────────


def compute_all(
    raw: Mapping[str, pd.DataFrame],
    normed: dict,
    meta,                                  # AomMeta — no annotation to dodge circular import
) -> dict[str, float | None]:
    """Compute the productivity indicators implemented in Tasks 2.1 + 2.2.

    Input Schema:
        raw: dict-of-DataFrames from `read_gtfs_zip` — needs at minimum
             "routes" with `route_id`.
        normed: NormedGTFS dict from `gtfs_normalize` — needs "stops",
                "stop_times", "trips", "calendar", "calendar_dates",
                "trip_id_coor", plus the normalized "routes".
        meta: AomMeta — unused by Tasks 2.1/2.2 but kept for signature symmetry
              with `density.compute_all` (which takes `meta` for
              area_km2 / population denominators).

    Output Schema:
        {
            "prod_kcc_year":             float (km, sum of F_3_KCC_Lignes grid),
            "prod_lines_count":          float (count of unique route_id in raw),
            "prod_stops_count":          float (count of physical stops, location_type=0),
            "prod_courses_day_avg":      float (avg daily trip executions over service window),
            "prod_peak_hour_courses":    float (max trips/hour during HPM/HPS, avg across days),
            "prod_service_amplitude":    float (hours, max(arr) − min(dep), avg across days),
            "prod_network_length_km":    float (km, Σ Haversine across unique undirected segments),
            "prod_peak_vehicles_needed": float (Σ_route ⌈round_trip_min / peak_headway_min⌉),
        }
        Missing/unavailable values resolve to None.
    """
    out: dict[str, float | None] = {}

    chain = _compute_chain(raw, normed)

    out["prod_kcc_year"] = _kcc_year(chain)
    out["prod_lines_count"] = float(raw["routes"]["route_id"].nunique())

    stops = normed["stops"]
    if "location_type" in stops.columns:
        physical = stops[stops["location_type"].fillna(0).astype(int) == 0]
    else:
        physical = stops
    out["prod_stops_count"] = float(physical["stop_id"].nunique())

    out["prod_courses_day_avg"] = _courses_day_avg(chain)
    out["prod_peak_hour_courses"] = _peak_hour_courses(chain)
    out["prod_service_amplitude"] = _service_amplitude(chain)
    out["prod_network_length_km"] = _network_length_km(chain)
    out["prod_peak_vehicles_needed"] = _peak_vehicles_needed(chain)

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Shared chain helper
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Chain:
    """Intermediates produced by the spatial+itinerary+sjt pipeline.

    All 8 fields are reused by the productivity indicators that need network
    structure. Frozen so accidental mutation by one indicator can't bleed
    into the next.

    Fields:
        AP:             areas piétonnes (point clusters), [id_ap_num, ...].
        AG:             areas géographiques (line-aware clusters).
        lignes:         normalized routes with id_ligne_num.
        courses:        full course table with sous_ligne, id_course_num,
                        h_dep_num, h_arr_num, DIST_Vol_Oiseau, etc.
        courses_export: MEF_course-shaped frame (export columns including
                        h_dep_num/h_arr_num as fractional days, id_service_num).
        lignes_export:  MEF_ligne-shaped frame.
        sjt:            service_jour_type result, [id_ligne_num,
                        id_service_num, <type_vac>, Date_GTFS].
        service_dates:  [id_service_num, Date_GTFS, Type_Jour, ...] one row
                        per (service, calendar date) pair active in the window.
        type_vac:       column name actually used (after fallback to
                        "Type_Jour" if the requested column was absent).
        itineraire_arc: per-course consecutive stop pairs, [id_course_num,
                        id_ligne_num, id_ag_num_a, id_ag_num_b, DIST_Vol_Oiseau
                        (meters), ...] — used by `_network_length_km` to
                        dedupe undirected geographic segments.
    """
    AP: pd.DataFrame
    AG: pd.DataFrame
    lignes: pd.DataFrame
    courses: pd.DataFrame
    courses_export: pd.DataFrame
    lignes_export: pd.DataFrame
    sjt: pd.DataFrame
    service_dates: pd.DataFrame
    type_vac: str
    itineraire_arc: pd.DataFrame


def _compute_chain(
    raw: Mapping[str, pd.DataFrame],
    normed: dict,
    type_vac: str = "Type_Jour",
) -> _Chain:
    """Run the spatial+itinerary+service-jour-type chain once.

    Reproduces worker.py:255-321 / pipeline.py:127-160 minus the file I/O
    and minus the spec §6.2 [skip] markers (which cannot be skipped here
    because `kcc_course_ligne` transitively requires AG/AP).

    Calendar provider is `NullCalendarProvider` (default `Dates`, no XLS
    holidays injected) — matches the d4 baselines. `type_vac` falls back
    to "Type_Jour" if the requested column isn't produced by
    `service_date_generate` (graceful degradation, mirrors worker.py:296-298).

    Input Schema:
        raw:    dict from `read_gtfs_zip`.
        normed: NormedGTFS dict from `gtfs_normalize`.
        type_vac: column name in service_dates to pivot on. Default "Type_Jour".

    Output: `_Chain` frozen dataclass (see fields above).
    """
    from app.services.gtfs_core.gtfs_norm import ligne_generate
    from app.services.gtfs_core.gtfs_spatial import ag_ap_generate_reshape
    from app.services.gtfs_core.gtfs_generator import (
        course_generate,
        itiarc_generate,
        itineraire_generate,
        service_date_generate,
        service_jour_type_generate,
    )
    from app.services.gtfs_core.gtfs_export import MEF_course, MEF_ligne
    from app.services.gtfs_core.pipeline import build_dates_table

    # 1. Spatial clustering — produces AP, AG.
    AP, AG, _marker = ag_ap_generate_reshape(normed["stops"])

    # 2. Lines / itinerary / arcs / courses (worker.py:262-274).
    lignes = ligne_generate(normed["routes"])
    itineraire = itineraire_generate(normed["stop_times"], AP, normed["trips"])
    itineraire_arc = itiarc_generate(itineraire, AG)
    courses = course_generate(itineraire, itineraire_arc)

    courses_export = MEF_course(courses, normed["trip_id_coor"])
    lignes_export = MEF_ligne(lignes, courses_export, AG)

    # 3. Service dates + jour-type (NullCalendarProvider equivalent).
    Dates = build_dates_table(normed["calendar"], normed["calendar_dates"])
    service_dates, _msg = service_date_generate(
        normed["calendar"], normed["calendar_dates"], Dates
    )
    if type_vac not in service_dates.columns:
        type_vac = "Type_Jour"

    sjt = service_jour_type_generate(service_dates, courses, type_vac)

    return _Chain(
        AP=AP,
        AG=AG,
        lignes=lignes,
        courses=courses,
        courses_export=courses_export,
        lignes_export=lignes_export,
        sjt=sjt,
        service_dates=service_dates,
        type_vac=type_vac,
        itineraire_arc=itineraire_arc,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Indicator helpers
# ──────────────────────────────────────────────────────────────────────────────


def _kcc_year(chain: _Chain) -> float:
    """Spec §11 contract anchor: must match worker pipeline F_3_KCC_Lignes within 0.1%.

    Reproduces F_3_KCC_Lignes (worker.py:322-323) by piping the shared chain
    through `kcc_course_ligne`, then summing the pivot grid. `has_shp=False`
    matches the d4 baseline configuration.

    Returns: grand total of all KCC cells (km/year proxy).
    """
    from app.services.gtfs_core.gtfs_generator import kcc_course_ligne

    kcc_df = kcc_course_ligne(
        chain.sjt, chain.courses_export, chain.type_vac, chain.lignes_export, False
    )
    id_cols = {"id_ligne_num", "route_short_name", "route_long_name"}
    jt_cols = [c for c in kcc_df.columns if c not in id_cols]
    return float(kcc_df[jt_cols].sum().sum())


def _courses_day_avg(chain: _Chain) -> float | None:
    """Spec §5.1 A + §11 contract clause: Σ F_1_Nombre_Courses_Lignes.courses / total_days.

    Returns the F_1 pivot grand total (representative-day trip counts across all
    lines × jour-types) divided by total distinct dates in the service window.

    Note: this is NOT the average number of trip executions per calendar day.
    The spec contract defines `total_days` as the analysis window span and
    counts trips via the representative-day pivot, so the result reflects
    average trips weighted by jour-type composition rather than literal
    daily executions. The cross-product semantics ("trips executed per day")
    is a defensible alternative but would require a spec amendment.

    Input Schema (via chain):
        sjt, courses_export, type_vac, lignes_export — passed through to
            `nb_course_ligne` (canonical F_1 worker).
        service_dates: [id_service_num, Date_GTFS, ...] — for total_days count.
    Output: float (Σ F_1 / total_days) or None if no service dates / no F_1 data.
    """
    from app.services.gtfs_core.gtfs_generator import nb_course_ligne

    nb_df = nb_course_ligne(
        chain.sjt, chain.courses_export, chain.type_vac, chain.lignes_export,
    )
    id_cols = {"id_ligne_num", "route_short_name", "route_long_name"}
    val_cols = [c for c in nb_df.columns if c not in id_cols]
    if not val_cols:
        return None
    grand_total_trips = float(nb_df[val_cols].sum().sum())
    total_days = int(chain.service_dates["Date_GTFS"].nunique())
    if total_days == 0:
        return None
    return grand_total_trips / total_days


def _peak_hour_courses(chain: _Chain) -> float | None:
    """Spec §5.1 A: peak-hour trip count.

    For each calendar date in the service window, bucket all trip executions
    by their departure hour (floor of `h_dep_num × 24`). The peak-hour value
    for that date is the maximum count across the 4 peak hours
    (07h, 08h, 17h, 18h — i.e. HPM 07-09 and HPS 17-19, exclusive of the
    ending boundary). The indicator is the average of those daily peaks
    across all dates that have at least one peak-hour trip.

    Plan 2 Assumption A11 (derived design): per-date averaging is a defensible
    interpretation of the spec text but is not literally specified. The spec
    gives no explicit aggregation rule across calendar days, so we average
    daily peaks rather than report a single "max-peak-on-busiest-day" value.
    This produces a network-typical peak that absorbs weekly cycles
    (Sundays drag the mean down vs weekdays) — it's not a rush-hour maximum
    on the busiest weekday. Documented as an Assumption rather than spec-amended.

    Design choice: takes `chain` only (no separate `stop_times` arg) because
    `h_dep_num` on `courses_export` already contains the first-stop departure
    time (set by `course_generate` via aggregating `arrival_time` min over
    the trip's stops, then renamed in `MEF_course`).

    Input Schema (via chain):
        courses_export: [id_course_num, id_service_num, h_dep_num, ...]
                        h_dep_num is fractional day in [0, 1+) (>1 for
                        after-midnight services).
        service_dates:  [id_service_num, Date_GTFS, ...]
    Output: float (max peak-hour trips/day, averaged across dates) or None.
    """
    sd = chain.service_dates
    ce = chain.courses_export
    if sd.empty or ce.empty or "h_dep_num" not in ce.columns:
        return None

    # Each merged row = one trip execution on one calendar date.
    merged = ce[["id_course_num", "id_service_num", "h_dep_num"]].merge(
        sd[["id_service_num", "Date_GTFS"]], on="id_service_num"
    )
    if merged.empty:
        return None

    # Departure hour bucket. Modulo 24 to fold after-midnight services back
    # into the 24-hour clock (a course departing at 25:30 → bucket 1).
    merged = merged.copy()
    merged["dep_hour"] = (merged["h_dep_num"] * 24).astype(int) % 24

    peak_hours = (7, 8, 17, 18)
    peak = merged[merged["dep_hour"].isin(peak_hours)]
    if peak.empty:
        return None

    counts_per_date_hour = (
        peak.groupby(["Date_GTFS", "dep_hour"], as_index=False)["id_course_num"].count()
        .rename(columns={"id_course_num": "n"})
    )
    daily_peak = counts_per_date_hour.groupby("Date_GTFS")["n"].max()
    return float(daily_peak.mean())


def _service_amplitude(chain: _Chain) -> float | None:
    """Spec §5.1 A: service amplitude in hours, averaged across days.

    For each date with active service, amplitude = max(h_arr_num) −
    min(h_dep_num) across all trips active that day, in hours
    (multiplied by 24 since `h_*_num` are fractional days). Averaged
    across all dates in the service window that have at least one trip.

    h_arr_num can exceed 1.0 for after-midnight services — that's fine,
    the subtraction still produces the correct duration since h_dep_num
    of the same trip is anchored on the same day boundary.

    Plan 2 Assumption A10 (derived design): the literal spec wording is
    "max(stop_time) − min(stop_time)" (singular), which would suggest a
    single network-wide amplitude over the entire window. We instead
    compute per-date amplitudes and average them, which yields a "typical
    service day" amplitude rather than a window-spanning max. This avoids
    inflating amplitude when the window contains heterogeneous days
    (e.g. weekday late-night + weekend early-morning). Documented as an
    Assumption rather than spec-amended.

    Input Schema (via chain):
        courses_export: [id_course_num, id_service_num, h_dep_num, h_arr_num, ...]
        service_dates:  [id_service_num, Date_GTFS, ...]
    Output: float (hours, mean of per-date amplitudes) or None.
    """
    sd = chain.service_dates
    ce = chain.courses_export
    if sd.empty or ce.empty:
        return None
    if "h_dep_num" not in ce.columns or "h_arr_num" not in ce.columns:
        return None

    merged = ce[["id_service_num", "h_dep_num", "h_arr_num"]].merge(
        sd[["id_service_num", "Date_GTFS"]], on="id_service_num"
    )
    if merged.empty:
        return None

    per_day = merged.groupby("Date_GTFS").agg(
        dep_min=("h_dep_num", "min"),
        arr_max=("h_arr_num", "max"),
    )
    per_day["amplitude_hours"] = (per_day["arr_max"] - per_day["dep_min"]) * 24.0
    return float(per_day["amplitude_hours"].mean())


def _network_length_km(chain: _Chain) -> float | None:
    """Spec §5.1 A: sum of unique geographic segments across the network.

    Algorithm:
        1. Take all directed (id_ag_num_a, id_ag_num_b) consecutive-stop
           pairs from `chain.itineraire_arc`. Each row is one course's
           segment between two AG (geographic-cluster) stops.
        2. Convert to undirected via `frozenset({id_a, id_b})` so that
           A→B and B→A are folded into one edge — we want the geographic
           network length, not directed running length.
        3. Dedupe to one row per undirected pair (keeping the first
           `DIST_Vol_Oiseau` — values are populated by `itiarc_generate`
           via Haversine on AG centroids, so they are identical for both
           directions of the same undirected pair, modulo numerical
           rounding to 1m).
        4. Sum and convert from meters → km.

    Self-loops (id_ag_num_a == id_ag_num_b, distance 0) are kept (rare,
    but theoretically possible when two consecutive stops cluster into
    the same AG — they contribute 0 km and don't inflate the total).

    Input Schema (via chain):
        itineraire_arc: [id_course_num, id_ligne_num, id_ag_num_a,
                         id_ag_num_b, DIST_Vol_Oiseau (meters), ...]
        AG:             [id_ag_num, stop_lat, stop_lon, ...] (used only
                         to short-circuit on empty network).

    Output: float (km, total network length over unique undirected
            geographic segments) or None if no arcs / no AG.
    """
    AG = chain.AG
    ia = chain.itineraire_arc
    if AG is None or len(AG) == 0:
        return None
    if ia is None or len(ia) == 0:
        return None
    if "DIST_Vol_Oiseau" not in ia.columns:
        return None

    # Drop arcs with missing endpoints. itiarc_generate already drops NA on
    # id_ag_num_b but `_a` can still be NA in degenerate fixtures (e.g.
    # SEM has stops with no AG assignment after spatial clustering for
    # location_type != 0 entries that snuck into stop_times).
    valid = ia[["id_ag_num_a", "id_ag_num_b", "DIST_Vol_Oiseau"]].dropna(
        subset=["id_ag_num_a", "id_ag_num_b"]
    )
    if valid.empty:
        return None

    # Build undirected edge keys via vectorized min/max trick (faster than
    # frozenset comprehension and produces hashable composite keys).
    a = valid["id_ag_num_a"].astype("int64").to_numpy()
    b = valid["id_ag_num_b"].astype("int64").to_numpy()
    lo = pd.Series(a).where(a <= b, b)
    hi = pd.Series(a).where(a > b, b)

    edges = pd.DataFrame({
        "_lo": lo.values,
        "_hi": hi.values,
        "_dist_m": valid["DIST_Vol_Oiseau"].astype(float).to_numpy(),
    })
    # Take the first per undirected pair. itiarc_generate produces
    # symmetric Haversine values modulo np.around(_, 0), so picking
    # any duplicate is equivalent.
    unique_edges = edges.drop_duplicates(subset=["_lo", "_hi"], keep="first")
    total_meters = float(unique_edges["_dist_m"].sum())
    if total_meters <= 0:
        return None
    return total_meters / 1000.0


def _peak_vehicles_needed(chain: _Chain) -> float | None:
    """Spec §5.1 A: Σ_route ⌈peak_round_trip_time / peak_headway⌉.

    Computed per route (id_ligne_num) on a representative-day basis:
        - Peak hourly trip count for the route: max single-(date, hour)
          trip count over the four peak hours {7, 8, 17, 18}. Using
          (date, hour) pairs (not summing all dates) yields a true
          per-day peak; averaging or summing across dates would conflate
          weekly cycles and inflate vehicle requirement.
        - Peak headway (min) = 60 / peak_hourly_trip_count.
        - Round-trip time (min) = 2 × mean(course duration) for the
          route, in minutes. Course duration on `courses_export` is
          (h_arr_num − h_dep_num) in fractional days; multiplied by
          1440 → minutes. The 2× factor models a balanced
          out-and-back: the route's mean one-way running time × 2.
          This is approximate (real round-trip = layover + return)
          but matches the canonical fleet-sizing heuristic used in
          GTFS frequency analysis. **Plan 2 Assumption A12** —
          documented as a derived design choice rather than a
          spec-amended value. See spec §5.1 A note on round-trip
          definition ambiguity.
        - Vehicles needed for route = ⌈round_trip_min / peak_headway_min⌉.
        - Total = sum across routes that have peak service.

    Routes with no peak-hour service contribute 0 vehicles (excluded
    from sum). Routes with zero mean duration (degenerate case) are
    skipped to avoid divide-by-zero.

    Input Schema (via chain):
        courses_export: [id_course_num, id_ligne_num, id_service_num,
                         h_dep_num, h_arr_num, ...]
        sjt:            [id_ligne_num, id_service_num, <type_vac>,
                         Date_GTFS]

    Output: float (Σ vehicles needed at peak across all routes) or None
            if no route has peak service.
    """
    ce = chain.courses_export
    sjt = chain.sjt
    if ce is None or len(ce) == 0 or sjt is None or len(sjt) == 0:
        return None
    needed = {"id_ligne_num", "id_course_num", "id_service_num", "h_dep_num", "h_arr_num"}
    if not needed.issubset(ce.columns):
        return None

    # Expand each course to one row per active calendar date.
    merged = ce[list(needed)].merge(
        sjt[["id_ligne_num", "id_service_num", "Date_GTFS"]],
        on=["id_ligne_num", "id_service_num"],
    )
    if merged.empty:
        return None

    merged = merged.copy()
    # Departure-hour bucket, folded mod 24 to handle after-midnight services.
    merged["_dep_hour"] = (merged["h_dep_num"] * 24).astype(int) % 24
    # Course duration (minutes), clipped to non-negative.
    merged["_dur_min"] = (
        (merged["h_arr_num"] - merged["h_dep_num"]).clip(lower=0) * 1440.0
    )

    PEAK_HOURS = (7, 8, 17, 18)
    peak = merged[merged["_dep_hour"].isin(PEAK_HOURS)]
    if peak.empty:
        return None

    # Per (route, date, hour): trip count. Then per route: take max
    # across all (date, hour) pairs in the peak window.
    per_route_peak_count = (
        peak.groupby(["id_ligne_num", "Date_GTFS", "_dep_hour"])
            .size()
            .groupby(level="id_ligne_num")
            .max()
    )
    if per_route_peak_count.empty:
        return None

    # Mean course duration per route (minutes), across all dates and hours.
    per_route_mean_dur_min = (
        merged.groupby("id_ligne_num")["_dur_min"].mean()
    )

    total_vehicles = 0
    for route_id, peak_count in per_route_peak_count.items():
        if peak_count <= 0:
            continue
        mean_dur = per_route_mean_dur_min.get(route_id)
        if mean_dur is None or mean_dur <= 0:
            continue
        round_trip_min = 2.0 * float(mean_dur)
        peak_headway_min = 60.0 / float(peak_count)
        total_vehicles += math.ceil(round_trip_min / peak_headway_min)

    if total_vehicles <= 0:
        return None
    return float(total_vehicles)
