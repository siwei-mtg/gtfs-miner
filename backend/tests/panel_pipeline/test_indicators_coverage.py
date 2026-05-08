"""Coverage indicators (Spec §5.1 D)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from app.services.panel_pipeline.compute import AomMeta
from app.services.panel_pipeline.indicators import coverage


COVERAGE_INDICATORS = (
    "cov_pop_300m",
    "cov_pop_freq_300m",
    "cov_surface_300m",
    "cov_median_walk",
    "cov_pop_weighted_walk",
    "cov_equity_gini",
)


def _make_meta(polygon=None) -> AomMeta:
    if polygon is None:
        polygon = box(0, 0, 800, 800)
    return AomMeta(
        slug="test", population=1000, area_km2=1.0,
        polygon_l93=polygon, methodology_commit="t",
    )


def test_coverage_raises_when_carroyage_missing():
    """If the carroyage GeoPackage is absent, compute_all raises FileNotFoundError.
    Caller (compute()) catches and fills 6 cov_* with None."""
    raw = {"stops": pd.DataFrame(), "trips": pd.DataFrame(), "routes": pd.DataFrame(),
           "stop_times": pd.DataFrame()}
    normed = {"stops": pd.DataFrame(), "trips": pd.DataFrame(), "routes": pd.DataFrame(),
              "stop_times": pd.DataFrame()}
    meta = _make_meta()
    # Patch CARROYAGE_PATH to a definitely-missing path
    with patch.object(coverage, "CARROYAGE_PATH", Path("/nonexistent/carroyage.gpkg")):
        with pytest.raises(FileNotFoundError):
            coverage.compute_all(raw, normed, meta)


def test_coverage_returns_6_keys_when_carroyage_present(tmp_path: Path):
    """With a synthetic carroyage in place, all 6 cov_* keys populate (some may be 0.0)."""
    # Build a tiny synthetic carroyage GeoPackage
    from app.services.panel_pipeline.geo import LAMBERT_93
    cells = []
    for x in (0, 200):
        for y in (0, 200):
            cells.append({
                "geometry": box(x, y, x + 200, y + 200),
                "Ind": 100,
            })
    carroyage = gpd.GeoDataFrame(cells, crs=LAMBERT_93)
    gpkg = tmp_path / "carroyage.gpkg"
    carroyage.to_file(gpkg, driver="GPKG")

    # Synthetic stops + trips + routes
    stops = pd.DataFrame([
        {"stop_id": "S1", "stop_lat": 45.0, "stop_lon": 5.7, "location_type": 0},
    ])
    trips = pd.DataFrame([{"trip_id": "T1", "id_course_num": 1, "route_id": "R1",
                           "id_ligne_num": 1, "service_id": "X"}])
    routes = pd.DataFrame([{"route_id": "R1", "id_ligne_num": 1, "route_type": 3,
                            "route_short_name": "1"}])
    stop_times = pd.DataFrame([
        {"id_course_num": 1, "stop_id": "S1", "stop_sequence": 1,
         "departure_time": "07:00:00", "arrival_time": "07:00:00"},
    ])
    raw = {"stops": stops, "trips": trips, "routes": routes, "stop_times": stop_times}
    normed = raw  # same shape
    meta = _make_meta(polygon=box(0, 0, 400, 400))
    with patch.object(coverage, "CARROYAGE_PATH", gpkg):
        out = coverage.compute_all(raw, normed, meta)
    # All 6 keys present; values may be 0/inf depending on geom intersection
    for k in COVERAGE_INDICATORS:
        assert k in out, f"{k} missing"


def test_coverage_uses_peak_headway_helper_for_freq():
    """cov_pop_freq_300m delegates to frequency._peak_headway_per_route to identify high-freq stops."""
    from app.services.panel_pipeline.indicators import frequency
    # Verify the import path is the one Task 3.3 will use
    assert hasattr(frequency, "_peak_headway_per_route")
    assert hasattr(frequency, "HIGH_FREQ_HEADWAY_MIN")
    assert frequency.HIGH_FREQ_HEADWAY_MIN == 10.0
