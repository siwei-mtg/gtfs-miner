"""Unit tests for panel_pipeline.geo — synthetic Lambert-93 fixtures only.

These tests do NOT require the real INSEE carroyage GeoPackage or AOM
GeoJSON. They build a small grid + box AOM in EPSG:2154 directly so the
math is hand-verifiable.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from app.services.panel_pipeline.geo import (
    CARROYAGE_POP_COLUMN,
    LAMBERT_93,
    compute_coverage,
    gtfs_stops_to_geodataframe,
    load_aom_polygon,
    load_carroyage_200m,
)


def _make_grid(*, n_per_side: int = 3, cell_size: float = 200.0,
               origin: tuple[float, float] = (0.0, 0.0),
               pop_per_cell: float = 100.0) -> gpd.GeoDataFrame:
    """Build a square grid of `n_per_side`² cells, each with population 100."""
    cells = []
    for i in range(n_per_side):
        for j in range(n_per_side):
            x0 = origin[0] + i * cell_size
            y0 = origin[1] + j * cell_size
            cells.append({
                CARROYAGE_POP_COLUMN: pop_per_cell,
                "geometry": box(x0, y0, x0 + cell_size, y0 + cell_size),
            })
    return gpd.GeoDataFrame(cells, crs=LAMBERT_93)


def _make_aom_box(*, origin: tuple[float, float] = (0.0, 0.0),
                  side: float = 600.0) -> gpd.GeoDataFrame:
    """AOM polygon = square covering [origin, origin+side]² in Lambert-93."""
    return gpd.GeoDataFrame(
        {"Nom_AOM": ["TestAOM"]},
        geometry=[box(origin[0], origin[1], origin[0] + side, origin[1] + side)],
        crs=LAMBERT_93,
    )


# ---------- compute_coverage ----------


def test_compute_coverage_central_stop_3x3_grid() -> None:
    """Stop in middle of 3x3 200m grid + 300m buffer covers all 9 cells.

    Hand-checked math:
        - 9 cells × 200m × 200m = 0.36 km² AOM, pop = 9×100 = 900
        - 300m buffer from (300,300) covers entire 600x600 AOM
          (max corner distance = 424m, but cell-level intersect counts the
           cell as soon as ANY part of it touches the buffer; at 300m radius
           the circle reaches all 9 cells)
        - cov_pop_300m = 100%
        - cov_surface_300m = π·300² / 360000 ≈ 78.5%
        - cov_median_walk = 200m  (4 cells at 200, 4 at √(200²+200²)=283, 1 at 0)
        - cov_pop_weighted_walk = (0 + 4·200 + 4·283) / 9 ≈ 214.6m
    """
    grid = _make_grid(n_per_side=3)
    aom = _make_aom_box()
    stops = gpd.GeoDataFrame(geometry=[Point(300, 300)], crs=LAMBERT_93)

    out = compute_coverage(stops, grid, aom, buffer_m=300)

    assert out["stop_count"] == 1
    assert out["cell_count"] == 9
    assert out["total_pop"] == pytest.approx(900.0)
    assert out["total_surface_km2"] == pytest.approx(0.36, rel=1e-6)
    assert out["cov_pop_300m"] == pytest.approx(100.0, abs=1e-6)
    assert out["cov_surface_300m"] == pytest.approx(
        100.0 * math.pi * 300**2 / 360000, abs=0.5,
    )
    assert out["cov_median_walk"] == pytest.approx(200.0, abs=1.0)
    expected_weighted = (0 + 4 * 200 + 4 * math.hypot(200, 200)) / 9
    assert out["cov_pop_weighted_walk"] == pytest.approx(expected_weighted, abs=1.0)


def test_compute_coverage_no_stops_returns_inf_walk() -> None:
    grid = _make_grid(n_per_side=3)
    aom = _make_aom_box()
    stops = gpd.GeoDataFrame(geometry=[], crs=LAMBERT_93)

    out = compute_coverage(stops, grid, aom, buffer_m=300)

    assert out["cov_pop_300m"] == 0.0
    assert out["cov_surface_300m"] == 0.0
    assert math.isinf(out["cov_median_walk"])
    assert math.isinf(out["cov_pop_weighted_walk"])
    assert out["stop_count"] == 0
    assert out["cell_count"] == 9


def test_compute_coverage_clips_outside_aom() -> None:
    """Cells outside the AOM should NOT contribute to denominators."""
    # 5x5 grid covers (0..1000, 0..1000) but AOM only covers (0..600, 0..600)
    # so only the inner 3x3 = 9 cells are counted.
    grid = _make_grid(n_per_side=5)
    aom = _make_aom_box(side=600.0)
    stops = gpd.GeoDataFrame(geometry=[Point(300, 300)], crs=LAMBERT_93)

    out = compute_coverage(stops, grid, aom, buffer_m=300)

    # Only 9 cells × 100 = 900 population should count, not 25 × 100 = 2500
    assert out["total_pop"] == pytest.approx(900.0)
    assert out["cell_count"] == 9


def test_compute_coverage_reprojects_inputs_defensively() -> None:
    """Inputs in WGS84 should be silently re-projected to Lambert-93."""
    grid = _make_grid(n_per_side=3).to_crs("EPSG:4326")
    aom = _make_aom_box().to_crs("EPSG:4326")
    # Stop at the centroid of the AOM (in WGS84 after reprojection)
    aom_centroid_wgs84 = aom.geometry.centroid.iloc[0]
    stops = gpd.GeoDataFrame(geometry=[aom_centroid_wgs84], crs="EPSG:4326")

    out = compute_coverage(stops, grid, aom, buffer_m=300)

    # The reprojected math should still produce a sensible coverage > 0
    assert out["cov_pop_300m"] > 0
    assert out["stop_count"] == 1


# ---------- gtfs_stops_to_geodataframe ----------


def test_gtfs_stops_filters_non_physical() -> None:
    df = pd.DataFrame({
        "stop_id": ["a", "b", "c", "d"],
        "stop_lat": [48.85, 48.86, None, 48.88],
        "stop_lon": [2.35, 2.36, 2.37, 2.38],
        "location_type": [0, 1, 0, 0],
    })
    gdf = gtfs_stops_to_geodataframe(df)
    # location_type==1 (station) and lat==None dropped → only a, d
    assert sorted(gdf["stop_id"].tolist()) == ["a", "d"]
    assert gdf.crs.to_epsg() == 2154


def test_gtfs_stops_no_location_type_column() -> None:
    """When the column is absent, all rows with valid lat/lon are kept."""
    df = pd.DataFrame({
        "stop_id": ["a", "b"],
        "stop_lat": [48.85, 48.86],
        "stop_lon": [2.35, 2.36],
    })
    gdf = gtfs_stops_to_geodataframe(df)
    assert len(gdf) == 2


# ---------- load_carroyage_200m ----------


def test_load_carroyage_missing_file_raises_with_url() -> None:
    with pytest.raises(FileNotFoundError, match="insee.fr"):
        load_carroyage_200m(Path("/does/not/exist.gpkg"))


def test_load_carroyage_validates_pop_column(tmp_path: Path) -> None:
    """A GPKG without the 'Ind' column must raise ValueError."""
    fake = gpd.GeoDataFrame(
        {"WrongColumn": [1]},
        geometry=[box(0, 0, 200, 200)],
        crs=LAMBERT_93,
    )
    out = tmp_path / "fake.gpkg"
    fake.to_file(out, driver="GPKG")

    with pytest.raises(ValueError, match="Ind"):
        load_carroyage_200m(out)


# ---------- load_aom_polygon ----------


def test_load_aom_polygon_matches_unique_row(tmp_path: Path) -> None:
    aom = gpd.GeoDataFrame(
        {"Nom_AOM": ["A", "B", "C"]},
        geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100), box(400, 0, 500, 100)],
        crs=LAMBERT_93,
    )
    p = tmp_path / "aom.geojson"
    aom.to_file(p, driver="GeoJSON")

    out = load_aom_polygon(p, field="Nom_AOM", value="B")
    assert len(out) == 1
    assert out["Nom_AOM"].iloc[0] == "B"
    assert out.crs.to_epsg() == 2154


def test_load_aom_polygon_no_match_raises(tmp_path: Path) -> None:
    aom = gpd.GeoDataFrame(
        {"Nom_AOM": ["A"]}, geometry=[box(0, 0, 100, 100)], crs=LAMBERT_93,
    )
    p = tmp_path / "aom.geojson"
    aom.to_file(p, driver="GeoJSON")

    with pytest.raises(ValueError, match="No AOM row matched"):
        load_aom_polygon(p, field="Nom_AOM", value="ZZZ")


def test_load_aom_polygon_multiple_matches_raises(tmp_path: Path) -> None:
    aom = gpd.GeoDataFrame(
        {"Nom_AOM": ["A", "A"]},
        geometry=[box(0, 0, 100, 100), box(200, 0, 300, 100)],
        crs=LAMBERT_93,
    )
    p = tmp_path / "aom.geojson"
    aom.to_file(p, driver="GeoJSON")

    with pytest.raises(ValueError, match="Multiple AOM rows"):
        load_aom_polygon(p, field="Nom_AOM", value="A")


def test_load_aom_polygon_missing_file_raises_with_url() -> None:
    with pytest.raises(FileNotFoundError, match="data.gouv.fr"):
        load_aom_polygon(Path("/does/not/exist.geojson"), field="x", value="y")


def test_load_aom_polygon_unknown_field_raises(tmp_path: Path) -> None:
    aom = gpd.GeoDataFrame(
        {"Nom_AOM": ["A"]}, geometry=[box(0, 0, 100, 100)], crs=LAMBERT_93,
    )
    p = tmp_path / "aom.geojson"
    aom.to_file(p, driver="GeoJSON")

    with pytest.raises(ValueError, match="no 'siren_aom' column"):
        load_aom_polygon(p, field="siren_aom", value="123")


# ---------- compute_freq_coverage ----------


def test_compute_freq_coverage_subset_of_full():
    """If high-freq stops are a subset of all stops, freq coverage <= full coverage."""
    import geopandas as gpd
    from shapely.geometry import Point, box

    from app.services.panel_pipeline.geo import (
        LAMBERT_93, compute_coverage, compute_freq_coverage,
    )

    # Tiny synthetic AOM: 800m x 800m square at L93 origin
    aom = gpd.GeoDataFrame(geometry=[box(0, 0, 800, 800)], crs=LAMBERT_93)
    # 4-cell carroyage (200m x 200m each), 50 residents per cell
    cells = []
    for x in (0, 200, 400, 600):
        for y in (0, 200, 400, 600):
            cells.append({"geometry": box(x, y, x + 200, y + 200), "Ind": 50})
    carroyage = gpd.GeoDataFrame(cells, crs=LAMBERT_93)

    # 3 stops (one in each of 3 corners). All "high freq" -> reduces to compute_coverage
    stops_all = gpd.GeoDataFrame(
        geometry=[Point(100, 100), Point(700, 100), Point(700, 700)],
        crs=LAMBERT_93,
    )
    stops_freq_subset = stops_all.iloc[:1]  # only the 100,100 stop

    full = compute_coverage(stops_all, carroyage, aom)
    freq = compute_freq_coverage(stops_freq_subset, carroyage, aom)

    # Subset has <= full
    assert freq["cov_pop_freq_300m"] <= full["cov_pop_300m"]
    # Subset is non-zero (the corner stop covers ~1 cell)
    assert freq["cov_pop_freq_300m"] > 0


def test_compute_freq_coverage_empty_stops():
    """Empty high-freq stops -> cov_pop_freq_300m = 0.0."""
    import geopandas as gpd
    from shapely.geometry import box

    from app.services.panel_pipeline.geo import (
        LAMBERT_93, compute_freq_coverage,
    )

    aom = gpd.GeoDataFrame(geometry=[box(0, 0, 400, 400)], crs=LAMBERT_93)
    carroyage = gpd.GeoDataFrame(
        [{"geometry": box(0, 0, 200, 200), "Ind": 100}],
        crs=LAMBERT_93,
    )
    stops = gpd.GeoDataFrame(geometry=[], crs=LAMBERT_93)

    out = compute_freq_coverage(stops, carroyage, aom)
    assert out["cov_pop_freq_300m"] == 0.0


# ---------- compute_equity_gini ----------


def test_compute_equity_gini_uniform():
    """All cells equally covered -> Gini = 0."""
    import geopandas as gpd
    from shapely.geometry import box

    from app.services.panel_pipeline.geo import LAMBERT_93, compute_equity_gini

    cells = gpd.GeoDataFrame(
        [
            {"geometry": box(0, 0, 200, 200), "Ind": 100, "coverage_rate": 0.5},
            {"geometry": box(200, 0, 400, 200), "Ind": 100, "coverage_rate": 0.5},
            {"geometry": box(0, 200, 200, 400), "Ind": 100, "coverage_rate": 0.5},
            {"geometry": box(200, 200, 400, 400), "Ind": 100, "coverage_rate": 0.5},
        ],
        crs=LAMBERT_93,
    )
    out = compute_equity_gini(cells)
    assert out["cov_equity_gini"] == pytest.approx(0.0, abs=1e-6)


def test_compute_equity_gini_total_inequality():
    """One cell fully covered, rest fully uncovered -> Gini close to (n-1)/n."""
    import geopandas as gpd
    from shapely.geometry import box

    from app.services.panel_pipeline.geo import LAMBERT_93, compute_equity_gini

    cells = gpd.GeoDataFrame(
        [
            {"geometry": box(0, 0, 200, 200), "Ind": 100, "coverage_rate": 1.0},
            {"geometry": box(200, 0, 400, 200), "Ind": 100, "coverage_rate": 0.0},
            {"geometry": box(0, 200, 200, 400), "Ind": 100, "coverage_rate": 0.0},
            {"geometry": box(200, 200, 400, 400), "Ind": 100, "coverage_rate": 0.0},
        ],
        crs=LAMBERT_93,
    )
    out = compute_equity_gini(cells)
    # 4 equal-weight cells, 1 has rate=1, rest=0 -> Gini = 0.75 (3/4 inequality)
    assert out["cov_equity_gini"] == pytest.approx(0.75, abs=0.01)


def test_compute_equity_gini_handles_empty_input():
    """Empty input -> Gini = 0.0 (no inequality to measure)."""
    import geopandas as gpd
    from app.services.panel_pipeline.geo import LAMBERT_93, compute_equity_gini

    empty = gpd.GeoDataFrame(columns=["Ind", "coverage_rate"], geometry=[], crs=LAMBERT_93)
    out = compute_equity_gini(empty)
    assert out["cov_equity_gini"] == 0.0
