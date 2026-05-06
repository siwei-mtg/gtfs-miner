"""INSEE/IGN spatial loaders + coverage indicator computation.

Implements spec §5.1 D coverage indicators (`cov_pop_300m`,
`cov_surface_300m`, `cov_median_walk`, `cov_pop_weighted_walk`).

CRS contract:
    - GTFS stops arrive in EPSG:4326 (lon/lat).
    - INSEE carroyage 200m is published in EPSG:2154 (Lambert-93).
    - AOM polygons may be published in either; we normalise to Lambert-93
      because metric ops (buffer/area/distance) need a metric CRS.

Data shape contract (column names, exactly what we depend on):
    - carroyage_200m.gpkg: column ``Ind`` = total residents per 200m cell.
      All other columns ignored.
    - AOM polygons GeoJSON: any field that uniquely identifies the AOM
      (commonly ``siren_aom``, ``code_siren`` or ``Code_AOM``); caller
      passes the value + field name.
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union


LAMBERT_93 = "EPSG:2154"
WGS84 = "EPSG:4326"
CARROYAGE_POP_COLUMN = "Ind"  # INSEE Filosofi field for total residents
DEFAULT_BUFFER_M = 300


class CoverageIndicators(TypedDict):
    """Output of `compute_coverage`. Distances in metres, percentages 0-100."""
    cov_pop_300m: float
    cov_surface_300m: float
    cov_median_walk: float
    cov_pop_weighted_walk: float
    total_pop: float
    total_surface_km2: float
    stop_count: int
    cell_count: int


def load_carroyage_200m(
    gpkg_path: Path,
    *,
    bbox_l93: tuple[float, float, float, float] | None = None,
) -> gpd.GeoDataFrame:
    """Load INSEE Filosofi 200m carreaux GeoPackage in Lambert-93.

    Args:
        gpkg_path: Path to the unzipped Filosofi2017_carreaux_200m.gpkg.
        bbox_l93: Optional (xmin, ymin, xmax, ymax) in Lambert-93 to
            spatially filter at read time — keeps memory bounded when
            processing a single network (carroyage covers 250k+ km²).

    Returns:
        GeoDataFrame in EPSG:2154 with at minimum the ``geometry`` and
        ``Ind`` columns.

    Raises:
        FileNotFoundError if the file is missing.
        ValueError if the expected ``Ind`` column is absent.
    """
    if not gpkg_path.exists():
        raise FileNotFoundError(
            f"INSEE carroyage GeoPackage not found at {gpkg_path}. "
            "Download from https://www.insee.fr/fr/statistiques/6215138 "
            "(Filosofi2017_carreaux_200m_gpkg.zip, ~205 MB)."
        )
    gdf = gpd.read_file(gpkg_path, bbox=bbox_l93)
    if gdf.crs is None or gdf.crs.to_epsg() != 2154:
        gdf = gdf.to_crs(LAMBERT_93)
    if CARROYAGE_POP_COLUMN not in gdf.columns:
        raise ValueError(
            f"Carroyage missing required '{CARROYAGE_POP_COLUMN}' column "
            f"(found: {list(gdf.columns)[:10]}...)"
        )
    return gdf


def load_aom_polygon(
    geojson_path: Path,
    *,
    field: str,
    value: str | int,
) -> gpd.GeoDataFrame:
    """Load a single AOM polygon by attribute match, normalised to Lambert-93.

    Args:
        geojson_path: Cerema AOM GeoJSON (`les-autorites-organisatrices-de-la-mobilite-aom`).
        field: Attribute column to match on (e.g., 'siren_aom', 'Code_SIREN', 'Nom_AOM').
        value: Value to match (string or int — coerced to str for comparison).

    Returns:
        Single-row GeoDataFrame in EPSG:2154.

    Raises:
        FileNotFoundError if the file is missing.
        ValueError if no row or multiple rows match.
    """
    if not geojson_path.exists():
        raise FileNotFoundError(
            f"AOM polygon file not found at {geojson_path}. Download from "
            "https://www.data.gouv.fr/fr/datasets/les-autorites-organisatrices-de-la-mobilite-aom/"
        )
    gdf = gpd.read_file(geojson_path)
    if field not in gdf.columns:
        raise ValueError(
            f"AOM file has no '{field}' column. Available: {list(gdf.columns)}"
        )
    matched = gdf[gdf[field].astype(str) == str(value)]
    if len(matched) == 0:
        raise ValueError(f"No AOM row matched {field}={value!r}")
    if len(matched) > 1:
        raise ValueError(
            f"Multiple AOM rows matched {field}={value!r} ({len(matched)} rows). "
            "Pick a more specific field/value."
        )
    if matched.crs is None or matched.crs.to_epsg() != 2154:
        matched = matched.to_crs(LAMBERT_93)
    return matched.reset_index(drop=True)


def gtfs_stops_to_geodataframe(stops_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert a GTFS stops DataFrame (lon/lat columns) to a Lambert-93 GeoDataFrame.

    Filters to physical stops only (location_type == 0 or null).
    """
    df = stops_df.copy()
    if "location_type" in df.columns:
        df = df[df["location_type"].fillna(0).astype(int) == 0]
    df = df.dropna(subset=["stop_lat", "stop_lon"])
    geom = [Point(lon, lat) for lon, lat in zip(df["stop_lon"], df["stop_lat"])]
    return gpd.GeoDataFrame(df, geometry=geom, crs=WGS84).to_crs(LAMBERT_93)


def compute_coverage(
    stops: gpd.GeoDataFrame,
    carroyage: gpd.GeoDataFrame,
    aom_polygon: gpd.GeoDataFrame,
    *,
    buffer_m: int = DEFAULT_BUFFER_M,
) -> CoverageIndicators:
    """Compute the four AOM-restricted spatial coverage indicators.

    All inputs MUST be in EPSG:2154. We re-project defensively if not, but
    callers should normalise upstream so this stays a no-op.

    Algorithm:
        1. Clip carroyage to the AOM polygon (only cells inside the AOM
           contribute to denominator).
        2. Build the union of `buffer_m`-buffered stop geometries.
        3. cov_pop_300m   = population in cells overlapping the buffer / total AOM pop
           cov_surface_300m = AOM-clipped buffer area / total AOM area
           cov_median_walk = median centroid-to-nearest-stop distance
           cov_pop_weighted_walk = pop-weighted mean of the same distance
    """
    stops_l93 = stops if stops.crs and stops.crs.to_epsg() == 2154 else stops.to_crs(LAMBERT_93)
    carroyage_l93 = carroyage if carroyage.crs and carroyage.crs.to_epsg() == 2154 else carroyage.to_crs(LAMBERT_93)
    aom_l93 = aom_polygon if aom_polygon.crs and aom_polygon.crs.to_epsg() == 2154 else aom_polygon.to_crs(LAMBERT_93)

    # 1. Clip carroyage to AOM
    carroyage_in_aom = gpd.overlay(carroyage_l93, aom_l93, how="intersection")
    total_pop = float(carroyage_in_aom[CARROYAGE_POP_COLUMN].sum())
    total_surface_m2 = float(aom_l93.geometry.area.sum())

    if len(stops_l93) == 0:
        return CoverageIndicators(
            cov_pop_300m=0.0,
            cov_surface_300m=0.0,
            cov_median_walk=float("inf"),
            cov_pop_weighted_walk=float("inf"),
            total_pop=total_pop,
            total_surface_km2=total_surface_m2 / 1_000_000.0,
            stop_count=0,
            cell_count=int(len(carroyage_in_aom)),
        )

    # 2. Buffer union (single multipolygon)
    buffer_union = unary_union(stops_l93.geometry.buffer(buffer_m))
    buffer_gdf = gpd.GeoDataFrame(geometry=[buffer_union], crs=LAMBERT_93)

    # 3a. cov_pop_300m — population of cells that intersect the buffer.
    # We use cell-level intersection (all-or-nothing per cell) to mirror
    # how INSEE typically reports gridded coverage; this avoids over-
    # weighting partially-covered cells with their full population.
    covered_cells = gpd.sjoin(
        carroyage_in_aom, buffer_gdf, how="inner", predicate="intersects"
    )
    pop_in_buffer = float(covered_cells[CARROYAGE_POP_COLUMN].sum())
    cov_pop_300m = 100.0 * pop_in_buffer / total_pop if total_pop else 0.0

    # 3b. cov_surface_300m — buffer ∩ AOM area / total AOM area
    buffer_clip = gpd.overlay(buffer_gdf, aom_l93, how="intersection")
    surface_in_buffer = float(buffer_clip.geometry.area.sum())
    cov_surface_300m = 100.0 * surface_in_buffer / total_surface_m2 if total_surface_m2 else 0.0

    # 3c, 3d. Walk distances using cell centroids weighted by Ind.
    centroids_gdf = gpd.GeoDataFrame(
        carroyage_in_aom[[CARROYAGE_POP_COLUMN]].copy(),
        geometry=carroyage_in_aom.geometry.centroid,
        crs=LAMBERT_93,
    )
    nearest = gpd.sjoin_nearest(centroids_gdf, stops_l93, distance_col="walk_m")
    # sjoin_nearest can produce duplicates when a centroid is equidistant from
    # multiple stops; collapse to one row per centroid (min distance).
    nearest = nearest.groupby(level=0).first()
    cov_median_walk = float(nearest["walk_m"].median())
    pop_sum = float(nearest[CARROYAGE_POP_COLUMN].sum())
    cov_pop_weighted_walk = (
        float((nearest["walk_m"] * nearest[CARROYAGE_POP_COLUMN]).sum() / pop_sum)
        if pop_sum > 0 else float("inf")
    )

    return CoverageIndicators(
        cov_pop_300m=cov_pop_300m,
        cov_surface_300m=cov_surface_300m,
        cov_median_walk=cov_median_walk,
        cov_pop_weighted_walk=cov_pop_weighted_walk,
        total_pop=total_pop,
        total_surface_km2=total_surface_m2 / 1_000_000.0,
        stop_count=int(len(stops_l93)),
        cell_count=int(len(carroyage_in_aom)),
    )
