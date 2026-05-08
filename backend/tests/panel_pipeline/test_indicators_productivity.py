"""Per-indicator regression tests for productivity (Task 2.2).

Smoke + plausibility checks on the 3 count indicators added in Task 2.2.
Unlike `test_kcc_equivalence_contract.py` (which has the bit-equivalent
F_3_KCC_Lignes anchor), these are not frozen-value contracts — they are
order-of-magnitude regression locks. The plausibility bounds are wide
enough to absorb minor formula tweaks but tight enough to catch unit
errors (e.g. seconds vs hours, raw count vs density).
"""
from __future__ import annotations

import pytest

from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


_INDICATOR_IDS = (
    "prod_courses_day_avg",
    "prod_peak_hour_courses",
    "prod_service_amplitude",
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

    - courses_day_avg: typical urban network → 100-10000 trips/day.
      Bound widened to [50, 50_000] for small/large networks.
    - peak_hour_courses: typical peak hour → 10-2000 trips.
      Bound widened to [5, 5_000].
    - service_amplitude: hours, typical 12-22h.
      Bound widened to (4, 24) to allow night-bus-only and full-day networks.
    """
    out = run_panel_pipeline_for_fixture(fixture)

    cda = out["prod_courses_day_avg"]
    assert 50 < cda < 50_000, f"{fixture}: prod_courses_day_avg = {cda}"

    ph = out["prod_peak_hour_courses"]
    assert 5 < ph < 5_000, f"{fixture}: prod_peak_hour_courses = {ph}"

    amp = out["prod_service_amplitude"]
    assert 4 < amp < 24, f"{fixture}: prod_service_amplitude = {amp}"
