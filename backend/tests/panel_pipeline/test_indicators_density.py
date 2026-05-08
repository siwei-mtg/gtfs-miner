"""Density indicators (Spec §5.1 B). Pure ratios — easy to verify by hand."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


AOM_FIXTURES = yaml.safe_load(
    (Path(__file__).parent / "data" / "aom_meta_fixtures.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_density_all_4_present(fixture: str) -> None:
    """All 4 density indicators populate with non-None values on real fixtures."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind in ("dens_stops_km2", "dens_lines_100k_pop", "dens_kcc_capita", "dens_kcc_km2"):
        assert out.get(ind) is not None, f"{fixture}: {ind} missing"
        assert out[ind] > 0, f"{fixture}: {ind} = {out[ind]} (expected positive)"


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_density_matches_pure_arithmetic(fixture: str) -> None:
    """Density = ratio of productivity outputs to AomMeta — verify exact arithmetic."""
    out = run_panel_pipeline_for_fixture(fixture)
    aom = AOM_FIXTURES[fixture]
    pop, area = aom["population"], aom["area_km2"]
    kcc, lines, stops = out["prod_kcc_year"], out["prod_lines_count"], out["prod_stops_count"]
    assert out["dens_stops_km2"] == pytest.approx(stops / area, rel=1e-9)
    assert out["dens_lines_100k_pop"] == pytest.approx(lines / pop * 100_000, rel=1e-9)
    assert out["dens_kcc_capita"] == pytest.approx(kcc / pop, rel=1e-9)
    assert out["dens_kcc_km2"] == pytest.approx(kcc / area, rel=1e-9)


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_density_in_plausible_range(fixture: str) -> None:
    """Sanity bounds — density values should fall in typical urban transit ranges."""
    out = run_panel_pipeline_for_fixture(fixture)
    # stops_km2: typical urban networks 1-30
    assert 0.1 < out["dens_stops_km2"] < 50, \
        f"{fixture}: dens_stops_km2 = {out['dens_stops_km2']}"
    # lines_100k_pop: typical 5-50
    assert 1 < out["dens_lines_100k_pop"] < 100, \
        f"{fixture}: dens_lines_100k_pop = {out['dens_lines_100k_pop']}"
    # kcc_capita: typical 5-150 km/yr/person
    assert 0.001 < out["dens_kcc_capita"] < 200, \
        f"{fixture}: dens_kcc_capita = {out['dens_kcc_capita']}"
    # kcc_km2: typical 100-30000 km/yr/km²
    assert 1 < out["dens_kcc_km2"] < 100_000, \
        f"{fixture}: dens_kcc_km2 = {out['dens_kcc_km2']}"


def test_density_handles_zero_population_gracefully() -> None:
    """If meta has population=0 (e.g., misconfigured AOM), return None not crash."""
    from shapely.geometry import box
    from app.services.panel_pipeline.compute import AomMeta
    from app.services.panel_pipeline.indicators import density

    meta = AomMeta(slug="x", population=0, area_km2=10.0,
                   polygon_l93=box(0, 0, 1, 1), methodology_commit="t")
    prior = {"prod_kcc_year": 1.0, "prod_lines_count": 1.0, "prod_stops_count": 1.0}
    out = density.compute_all(prior, meta)
    assert out["dens_lines_100k_pop"] is None
    assert out["dens_kcc_capita"] is None
    # area-based ones should still work
    assert out["dens_stops_km2"] == pytest.approx(0.1)
    assert out["dens_kcc_km2"] == pytest.approx(0.1)
