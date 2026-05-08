"""Anchor + per-indicator regression tests for productivity (Task 2.2).

Mix of two test types:

1. **Anchor (frozen-value) test for `prod_courses_day_avg`** — spec §11
   contract clause line 865 requires `prod_courses_day_avg ↔
   Σ F_1_Nombre_Courses_Lignes.courses / total_days`. This is enforced
   exactly the same way as `test_kcc_equivalence_contract.py` enforces the
   F_3_KCC_Lignes contract. Without this, drift slips through silently
   (and would propagate to `dens_kcc_*` numerators in Task 2.4).

2. **Plausibility (order-of-magnitude) checks** for
   `prod_peak_hour_courses` and `prod_service_amplitude` — these
   indicators carry Plan 2 Assumptions A10/A11 (per-date averaging),
   so they are not bit-equivalent to a canonical worker output.
   Bounds are wide enough to absorb minor formula tweaks but tight
   enough to catch unit errors (seconds vs hours, raw count vs density).
"""
from __future__ import annotations

import pytest

from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


_INDICATOR_IDS = (
    "prod_courses_day_avg",
    "prod_peak_hour_courses",
    "prod_service_amplitude",
)


# Values frozen at the Task 2.2 fix commit (spec §11 contract enforcement).
# To update: re-run `run_panel_pipeline_for_fixture`, verify the new values
# are explainable (e.g. via spec-formula recomputation against
# `backend/storage/discovery/d4_kcc/baselines.json[<fixture>][courses_grand_total]
# / total_days`), and only then update these constants.
EXPECTED_COURSES_DAY_AVG: dict[str, float | None] = {
    "sem":   309.6831683168317,    # = 31278 / 101 (F_1 grand total / total_days)
    "solea": 132.38095238095238,   # = 13900 / 105
    "ginko":  18.0,                # = 486   / 27
}


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_prod_courses_day_avg_anchor(fixture: str) -> None:
    """Spec §11 contract: prod_courses_day_avg = Σ F_1.courses / total_days, ±0.1%."""
    expected = EXPECTED_COURSES_DAY_AVG[fixture]
    assert expected is not None, f"Anchor not yet set for {fixture}"
    out = run_panel_pipeline_for_fixture(fixture)
    actual = out["prod_courses_day_avg"]
    assert actual is not None, f"{fixture}: prod_courses_day_avg is None"
    assert abs(actual - expected) / expected < 0.001, (
        f"{fixture}: panel={actual:.2f} vs anchor={expected:.2f} "
        f"({100*abs(actual-expected)/expected:.3f}% drift)"
    )


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_productivity_counts_present_and_positive(fixture: str) -> None:
    """All 3 new indicators populate with positive values on real fixtures."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind_id in _INDICATOR_IDS:
        assert ind_id in out, f"{fixture}: {ind_id} missing"
        assert out[ind_id] is not None, f"{fixture}: {ind_id} is None"
        assert out[ind_id] > 0, f"{fixture}: {ind_id} = {out[ind_id]} (expected positive)"


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_productivity_counts_in_plausible_range(fixture: str) -> None:
    """Sanity bounds on output magnitudes.

    - courses_day_avg: spec §11 contract = Σ F_1.courses / total_days.
      For tiny fixtures (ginko = 6 lines, ~18 trips/day on the
      representative-day pivot) the value can be small. Bound widened
      to [10, 50_000]. The anchor test
      `test_prod_courses_day_avg_anchor` is the real contract enforcement
      — this bound only catches order-of-magnitude regressions.
    - peak_hour_courses: typical peak hour → 10-2000 trips.
      Bound widened to [5, 5_000].
    - service_amplitude: hours, typical 12-22h.
      Bound widened to (4, 24) to allow night-bus-only and full-day networks.
    """
    out = run_panel_pipeline_for_fixture(fixture)

    cda = out["prod_courses_day_avg"]
    assert 10 < cda < 50_000, f"{fixture}: prod_courses_day_avg = {cda}"

    ph = out["prod_peak_hour_courses"]
    assert 5 < ph < 5_000, f"{fixture}: prod_peak_hour_courses = {ph}"

    amp = out["prod_service_amplitude"]
    assert 4 < amp < 24, f"{fixture}: prod_service_amplitude = {amp}"


# ──────────────────────────────────────────────────────────────────────────────
# Task 2.3 — advanced indicators (network length + peak vehicles needed)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_productivity_advanced_present_and_positive(fixture: str) -> None:
    """prod_network_length_km + prod_peak_vehicles_needed populate with positive values."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind_id in ("prod_network_length_km", "prod_peak_vehicles_needed"):
        assert ind_id in out, f"{fixture}: {ind_id} missing"
        assert out[ind_id] is not None, f"{fixture}: {ind_id} is None"
        assert out[ind_id] > 0, f"{fixture}: {ind_id} = {out[ind_id]}"


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_productivity_advanced_in_plausible_range(fixture: str) -> None:
    """Sanity bounds on output magnitudes."""
    out = run_panel_pipeline_for_fixture(fixture)
    # network_length_km: typical urban networks 50-2000 km
    assert 30 < out["prod_network_length_km"] < 5_000, \
        f"{fixture}: prod_network_length_km = {out['prod_network_length_km']}"
    # peak_vehicles_needed: typical urban networks 20-2000 vehicles
    assert 3 < out["prod_peak_vehicles_needed"] < 5_000, \
        f"{fixture}: prod_peak_vehicles_needed = {out['prod_peak_vehicles_needed']}"
