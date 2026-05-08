"""Environment env_co2_year_estimated (Spec §5.1 H, Plan 2 Task 5.5)."""
from __future__ import annotations

import pytest

from app.services.panel_pipeline.indicators import environment
from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


# ──────────────────────────────────────────────────────────────────────────────
# Fixture-driven tests (real GTFS feeds → end-to-end indicator)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_env_co2_present_and_positive(fixture: str) -> None:
    """env_co2_year_estimated populates with a positive value (tCO2/year)."""
    out = run_panel_pipeline_for_fixture(fixture)
    assert "env_co2_year_estimated" in out
    assert out["env_co2_year_estimated"] is not None
    assert out["env_co2_year_estimated"] > 0


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_env_co2_in_plausible_range(fixture: str) -> None:
    """tCO2/year for the analysis window. Annualization factor varies; sanity-check magnitude.

    SEM has 364 km network × ~50k bus-km/year × 110 kgCO2 ÷ 1000 ≈ 5.5 ktCO2 typical.
    Smaller networks scale down. Test window: 0.001 to 100_000 tCO2.
    """
    out = run_panel_pipeline_for_fixture(fixture)
    assert 0.001 < out["env_co2_year_estimated"] < 100_000


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic unit tests — exercise the pure formula
# ──────────────────────────────────────────────────────────────────────────────


def test_env_co2_pure_bus_synthetic() -> None:
    """1000 km bus → 110 kgCO2/km → 110 tCO2."""
    prior = {"_kcc_by_route_type": {3: 1000.0}}
    out = environment.compute_all(prior)
    assert out["env_co2_year_estimated"] == pytest.approx(110.0)


def test_env_co2_mixed_modes_synthetic() -> None:
    """100 km tram (4.5 kg/km) + 200 km bus (110 kg/km) = 22.45 tCO2."""
    prior = {"_kcc_by_route_type": {0: 100.0, 3: 200.0}}
    out = environment.compute_all(prior)
    expected_t = (100 * 4.5 + 200 * 110.0) / 1000.0
    assert out["env_co2_year_estimated"] == pytest.approx(expected_t)


def test_env_co2_unknown_route_type_uses_default() -> None:
    """An unknown route_type (e.g., 99) falls back to the YAML `default` factor (110)."""
    prior = {"_kcc_by_route_type": {99: 100.0}}
    out = environment.compute_all(prior)
    expected_t = 100 * 110.0 / 1000.0
    assert out["env_co2_year_estimated"] == pytest.approx(expected_t)


def test_env_co2_returns_none_when_kcc_missing() -> None:
    """No `_kcc_by_route_type` sentinel → return None (productivity didn't run)."""
    out = environment.compute_all({})
    assert out["env_co2_year_estimated"] is None
