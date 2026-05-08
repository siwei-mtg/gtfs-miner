"""Frequency & speed indicators (Spec §5.1 E). Plan 2 Task 3.2."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


FREQ_INDICATORS = (
    "freq_peak_headway_median",
    "freq_high_freq_lines_pct",
    "freq_daily_service_hours",
    "freq_commercial_speed_kmh",
)


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_frequency_all_4_present(fixture: str) -> None:
    """All 4 frequency indicators populate with non-None positive values."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind in FREQ_INDICATORS:
        assert ind in out, f"{fixture}: {ind} missing"
        assert out[ind] is not None, f"{fixture}: {ind} is None"
        assert out[ind] > 0, f"{fixture}: {ind} = {out[ind]}"


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_frequency_in_plausible_range(fixture: str) -> None:
    """Sanity bounds for each indicator (urban transit benchmarks)."""
    out = run_panel_pipeline_for_fixture(fixture)
    # peak_headway_median: typical urban networks 5-30 min
    assert 1 < out["freq_peak_headway_median"] < 60, \
        f"{fixture}: peak_headway = {out['freq_peak_headway_median']}"
    # high_freq_lines_pct: urban networks may have 0-50%
    assert 0 <= out["freq_high_freq_lines_pct"] <= 100, \
        f"{fixture}: high_freq = {out['freq_high_freq_lines_pct']}"
    # daily_service_hours: 8-22h typical
    assert 4 < out["freq_daily_service_hours"] < 24, \
        f"{fixture}: service_hours = {out['freq_daily_service_hours']}"
    # commercial_speed_kmh: 10-50 km/h for urban transit
    assert 5 < out["freq_commercial_speed_kmh"] < 80, \
        f"{fixture}: comm_speed = {out['freq_commercial_speed_kmh']}"


def test_peak_headway_per_route_returns_dict() -> None:
    """Task 3.3 contract: _peak_headway_per_route returns a dict keyed by route id."""
    from app.services.gtfs_core.gtfs_norm import gtfs_normalize
    from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
    from app.services.panel_pipeline.indicators import frequency

    sem_zip = (
        Path(__file__).resolve().parents[1]
        / "Resources" / "raw" / "SEM-GTFS(2).zip"
    )
    raw = read_gtfs_zip(sem_zip)
    normed = gtfs_normalize(raw)

    headways = frequency._peak_headway_per_route(raw, normed)
    assert isinstance(headways, dict)
    assert len(headways) > 0  # SEM has >= 1 route with peak service

    # Every key must be a Python int (Task 3.3 will iterate ints).
    assert all(isinstance(k, int) for k in headways), \
        f"non-int keys: {[k for k in headways if not isinstance(k, int)]}"

    # Some routes return numeric headway, others may return None.
    valid = [h for h in headways.values() if h is not None]
    assert len(valid) > 0, "expected >= 1 route with peak service in SEM"
    # All valid headways are positive minutes.
    assert all(h > 0 for h in valid), \
        f"non-positive headway: {[h for h in valid if h <= 0]}"
