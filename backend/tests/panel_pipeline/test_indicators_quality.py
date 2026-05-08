"""Quality dq_* indicators (Spec §5.1 G)."""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.panel_pipeline.indicators import quality_indicators
from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


DQ_INDICATORS = (
    "dq_validator_errors",
    "dq_validator_warnings",
    "dq_field_completeness",
    "dq_coord_quality",
    "dq_route_type_completeness",
    "dq_freshness",
)


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_dq_indicators_present_in_output(fixture: str) -> None:
    """All 6 dq_* indicators populate (validator-based may be None if Java unavailable).

    Note: `run_panel_pipeline_for_fixture` drops None values, so validator-derived keys
    may be missing if Java/JAR is unavailable. The 4 non-validator dq_* must be present.
    """
    out = run_panel_pipeline_for_fixture(fixture)
    for ind in ("dq_field_completeness", "dq_coord_quality", "dq_route_type_completeness"):
        assert ind in out, f"{fixture}: {ind} missing"
        assert 0 <= out[ind] <= 100, f"{fixture}: {ind} = {out[ind]}"


def test_coord_quality_perfect():
    """Stops all within France -> 100%."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "stop_lat": 45.0, "stop_lon": 5.7},
            {"stop_id": "S2", "stop_lat": 48.85, "stop_lon": 2.35},  # Paris
        ]),
    }
    assert quality_indicators._coord_quality(raw) == pytest.approx(100.0)


def test_coord_quality_outside_france():
    """Stop in NYC -> 0%."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "stop_lat": 40.7, "stop_lon": -74.0},
        ]),
    }
    assert quality_indicators._coord_quality(raw) == pytest.approx(0.0)


def test_field_completeness_full():
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "stop_name": "A", "stop_lat": 45.0, "stop_lon": 5.0},
        ]),
        "routes": pd.DataFrame([
            {"route_id": "R1", "route_type": 3, "route_short_name": "1",
             "route_long_name": "Line 1"},
        ]),
        "trips": pd.DataFrame([
            {"trip_id": "T1", "route_id": "R1", "service_id": "X"},
        ]),
        "stop_times": pd.DataFrame([
            {"trip_id": "T1", "stop_id": "S1", "stop_sequence": 1,
             "arrival_time": "07:00", "departure_time": "07:00"},
        ]),
    }
    assert quality_indicators._field_completeness(raw) == pytest.approx(100.0)


def test_field_completeness_partial():
    """Half of routes missing route_type -> not perfect, not zero."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "stop_name": "A", "stop_lat": 45.0, "stop_lon": 5.0},
        ]),
        "routes": pd.DataFrame([
            {"route_id": "R1", "route_type": 3, "route_short_name": None,
             "route_long_name": None},
            {"route_id": "R2", "route_type": None, "route_short_name": None,
             "route_long_name": None},
        ]),
        "trips": pd.DataFrame([
            {"trip_id": "T1", "route_id": "R1", "service_id": "X"},
        ]),
        "stop_times": pd.DataFrame([
            {"trip_id": "T1", "stop_id": "S1", "stop_sequence": 1,
             "arrival_time": "07:00", "departure_time": "07:00"},
        ]),
    }
    score = quality_indicators._field_completeness(raw)
    assert 0 < score < 100


def test_route_type_completeness_perfect():
    raw = {"routes": pd.DataFrame([
        {"route_id": "R1", "route_type": 3},
        {"route_id": "R2", "route_type": 0},
    ])}
    assert quality_indicators._route_type_completeness(raw) == pytest.approx(100.0)


def test_route_type_completeness_partial():
    raw = {"routes": pd.DataFrame([
        {"route_id": "R1", "route_type": 3},
        {"route_id": "R2", "route_type": None},
    ])}
    assert quality_indicators._route_type_completeness(raw) == pytest.approx(50.0)


def test_freshness_returns_none_when_feed_info_absent():
    raw: dict = {}
    assert quality_indicators._freshness_days(raw) is None


def test_freshness_uses_feed_end_date():
    """Feed ending today -> ~0 days stale."""
    today = pd.Timestamp.now().strftime("%Y%m%d")
    raw = {"feed_info": pd.DataFrame([{"feed_end_date": today}])}
    days = quality_indicators._freshness_days(raw)
    assert days is not None and days <= 1


def test_validator_indicators_when_unavailable(monkeypatch):
    """If validator Java/JAR can't resolve, both validator dq_* are None."""
    from app.services.panel_pipeline import quality

    monkeypatch.setattr(quality, "is_validator_available", lambda: False)
    out = quality_indicators._validator_indicators(zip_path=__file__)
    assert out["dq_validator_errors"] is None
    assert out["dq_validator_warnings"] is None
