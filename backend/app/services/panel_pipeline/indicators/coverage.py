"""Spec §5.1 D. Coverage indicators (6 items).

Wraps panel_pipeline.geo machinery. The high-frequency stops filter for
cov_pop_freq_300m delegates to frequency._peak_headway_per_route (Task 3.2).

Plan 2 §6.2: when the INSEE carroyage GeoPackage is absent, raises
FileNotFoundError so the caller (compute()) can degrade gracefully and
fill all 6 cov_* with None + errors["..."] = "data_file_missing: ...".
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import geopandas as gpd
import pandas as pd

from app.services.panel_pipeline.geo import (
    CARROYAGE_POP_COLUMN,
    DEFAULT_BUFFER_M,
    LAMBERT_93,
    compute_coverage,
    compute_equity_gini,
    compute_freq_coverage,
    gtfs_stops_to_geodataframe,
    load_carroyage_200m,
)


CARROYAGE_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "Filosofi2017_carreaux_200m.gpkg"
)


def compute_all(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
    meta,                                 # AomMeta — no annotation to dodge circular import
) -> dict[str, float | None]:
    """Compute all 6 coverage indicators.

    Args:
        raw: Output of read_gtfs_zip.
        normed: Output of gtfs_normalize.
        meta: AomMeta with polygon_l93 (Shapely geometry in EPSG:2154).

    Returns:
        {indicator_id: value}. cov_median_walk and cov_pop_weighted_walk are in
        meters; the 4 percentage indicators are in [0, 100]; cov_equity_gini in [0, 1].

    Raises:
        FileNotFoundError if CARROYAGE_PATH does not exist. Caller (compute())
        catches this and fills all 6 keys as None.
    """
    if not CARROYAGE_PATH.exists():
        raise FileNotFoundError(
            f"INSEE carroyage GeoPackage not found at {CARROYAGE_PATH}. "
            "Required for coverage indicators. See geo.load_carroyage_200m for download."
        )

    # 1. AOM polygon
    aom = gpd.GeoDataFrame(geometry=[meta.polygon_l93], crs=LAMBERT_93)

    # 2. Spatially-clipped carroyage (bbox to keep memory bounded)
    bbox = tuple(aom.total_bounds.tolist())
    carro = load_carroyage_200m(CARROYAGE_PATH, bbox_l93=bbox)

    # 3. All stops (location_type=0) → GeoDataFrame in EPSG:2154
    stops = normed.get("stops")
    if stops is None or len(stops) == 0:
        return _empty_result()
    stops_gdf = gtfs_stops_to_geodataframe(stops)
    if len(stops_gdf) == 0:
        return _empty_result()

    # 4. Base coverage indicators
    base = compute_coverage(stops_gdf, carro, aom)

    # 5. High-frequency stops subset for cov_pop_freq_300m
    freq_subset = _high_freq_stops(raw, normed, stops_gdf)
    freq = (
        compute_freq_coverage(freq_subset, carro, aom)
        if len(freq_subset) > 0
        else {"cov_pop_freq_300m": 0.0}
    )

    # 6. Per-cell coverage_rate annotation for Gini
    carro_in_aom = gpd.overlay(carro, aom, how="intersection")
    if len(carro_in_aom) == 0:
        return {
            "cov_pop_300m": base["cov_pop_300m"],
            "cov_pop_freq_300m": freq["cov_pop_freq_300m"],
            "cov_surface_300m": base["cov_surface_300m"],
            "cov_median_walk": base["cov_median_walk"],
            "cov_pop_weighted_walk": base["cov_pop_weighted_walk"],
            "cov_equity_gini": None,
        }
    buffer_union = stops_gdf.geometry.buffer(DEFAULT_BUFFER_M).union_all()
    carro_in_aom["coverage_rate"] = (
        carro_in_aom.geometry.intersects(buffer_union).astype(float)
    )
    gini = compute_equity_gini(carro_in_aom)

    return {
        "cov_pop_300m": base["cov_pop_300m"],
        "cov_pop_freq_300m": freq["cov_pop_freq_300m"],
        "cov_surface_300m": base["cov_surface_300m"],
        "cov_median_walk": base["cov_median_walk"],
        "cov_pop_weighted_walk": base["cov_pop_weighted_walk"],
        "cov_equity_gini": gini["cov_equity_gini"],
    }


def _high_freq_stops(
    raw: Mapping[str, pd.DataFrame],
    normed: Mapping[str, pd.DataFrame],
    stops_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Return the GeoDataFrame of stops served by ≥1 high-frequency route.

    Plan 2 Assumption A7: route is "high-frequency" iff median peak headway ≤ 10 min.
    Reuses frequency._peak_headway_per_route to keep the threshold logic in one place.
    """
    from app.services.panel_pipeline.indicators import frequency
    headways = frequency._peak_headway_per_route(raw, normed)
    high_freq_route_ids = {
        rid for rid, h in headways.items()
        if h is not None and h <= frequency.HIGH_FREQ_HEADWAY_MIN
    }
    if not high_freq_route_ids:
        return stops_gdf.iloc[0:0]   # empty subset

    stop_times = normed.get("stop_times")
    trips = normed.get("trips")
    if stop_times is None or trips is None:
        return stops_gdf.iloc[0:0]
    if "id_course_num" not in stop_times.columns or "id_ligne_num" not in trips.columns:
        return stops_gdf.iloc[0:0]

    high_freq_trips = trips[trips["id_ligne_num"].isin(high_freq_route_ids)]
    if len(high_freq_trips) == 0:
        return stops_gdf.iloc[0:0]

    high_freq_stop_ids = (
        stop_times[stop_times["id_course_num"].isin(high_freq_trips["id_course_num"])]
        ["stop_id"].astype(str).unique()
    )
    return stops_gdf[stops_gdf["stop_id"].astype(str).isin(set(high_freq_stop_ids))]


def _empty_result() -> dict[str, float | None]:
    """Coverage defaults when we have a carroyage but no usable stops.

    Percentages report 0.0 (computed and zero — accurate for "no stops"),
    walk distances report None (undefined when there are no stops to walk to),
    Gini reports 0.0 (homogeneously uncovered = perfectly equitable).
    """
    return {
        "cov_pop_300m": 0.0,
        "cov_pop_freq_300m": 0.0,
        "cov_surface_300m": 0.0,
        "cov_median_walk": None,
        "cov_pop_weighted_walk": None,
        "cov_equity_gini": 0.0,
    }
