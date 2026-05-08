"""Spec §5.1 A. Productivity indicators (8 items).

Phase 2 Task 2.1 implemented 3 of 8:
    prod_kcc_year, prod_lines_count, prod_stops_count.

Phase 2 Task 2.2 adds 3 more (this file):
    prod_courses_day_avg, prod_peak_hour_courses, prod_service_amplitude.

Task 2.3 will fill the remaining 2 (prod_network_length_km, prod_peak_vehicles_needed).

Implementation note (Task 2.2 refactor): the chain that produces the KCC pivot
(`AP, AG, lignes, courses, courses_export, lignes_export, sjt, service_dates`)
is reused by the new count indicators. To avoid running it 3-4× per
`compute_all` call, it has been extracted into `_compute_chain` and the
intermediates packaged in a frozen `_Chain` dataclass. `_kcc_year` is now a
thin pivot-summation over `chain`; the new indicator helpers take `chain`
plus `normed` (for `stop_times` access where needed) and produce floats.
"""
from __future__ import annotations

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
            "prod_kcc_year":          float (km, sum of F_3_KCC_Lignes grid),
            "prod_lines_count":       float (count of unique route_id in raw),
            "prod_stops_count":       float (count of physical stops, location_type=0),
            "prod_courses_day_avg":   float (avg daily trip executions over service window),
            "prod_peak_hour_courses": float (max trips/hour during HPM/HPS, avg across days),
            "prod_service_amplitude": float (hours, max(arr) − min(dep), avg across days),
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
    """Spec §5.1 A: average daily trip executions across the service window.

    Each (course, date) pair where the course's service is active on that
    date counts as one trip execution. Total executions / number of distinct
    calendar dates in the window = average trips per day.

    This is a network-wide measure, not per-line, so it does not use the
    representative-day pivot from `service_jour_type` (which would
    under-count days where multiple jour-types coexist). It uses the raw
    `service_dates` cross-product instead.

    Input Schema (via chain):
        courses:       [id_course_num, id_service_num, ...]
        service_dates: [id_service_num, Date_GTFS, ...]
    Output: float (avg trips per day) or None if no service dates.
    """
    sd = chain.service_dates
    if sd.empty:
        return None
    total_days = sd["Date_GTFS"].nunique()
    if total_days == 0:
        return None
    # Each row of merged frame = one (course, date) execution.
    merged = chain.courses[["id_course_num", "id_service_num"]].merge(
        sd[["id_service_num", "Date_GTFS"]], on="id_service_num"
    )
    total_executions = float(len(merged))
    return total_executions / float(total_days) if total_days > 0 else None


def _peak_hour_courses(chain: _Chain) -> float | None:
    """Spec §5.1 A: peak-hour trip count.

    For each calendar date in the service window, bucket all trip executions
    by their departure hour (floor of `h_dep_num × 24`). The peak-hour value
    for that date is the maximum count across the 4 peak hours
    (07h, 08h, 17h, 18h — i.e. HPM 07-09 and HPS 17-19, exclusive of the
    ending boundary). The indicator is the average of those daily peaks
    across all dates that have at least one peak-hour trip.

    Returning a per-date average rather than a representative-day value
    averages over weekly cycles (Sundays drag the mean down vs weekdays);
    that's the spec intent — it's a network-typical peak, not a rush-hour
    maximum on the busiest weekday.

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
