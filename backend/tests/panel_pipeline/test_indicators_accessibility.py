"""Accessibility indicators (Spec §5.1 F)."""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


ACC_INDICATORS = ("acc_wheelchair_stops_pct", "acc_wheelchair_trips_pct")


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_accessibility_present_in_output(fixture: str) -> None:
    """Both accessibility indicators populate (may be 0.0 if data is missing on the fixture)."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind in ACC_INDICATORS:
        assert ind in out, f"{fixture}: {ind} missing"
        assert out[ind] is not None, f"{fixture}: {ind} is None"
        assert 0.0 <= out[ind] <= 100.0, f"{fixture}: {ind} = {out[ind]}"


def test_accessibility_pure_synthetic_all_accessible():
    """All stops wheelchair_boarding=1, all trips wheelchair_accessible=1 -> 100%."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "wheelchair_boarding": 1, "location_type": 0},
            {"stop_id": "S2", "wheelchair_boarding": 1, "location_type": 0},
        ]),
        "trips": pd.DataFrame([
            {"trip_id": "T1", "wheelchair_accessible": 1},
            {"trip_id": "T2", "wheelchair_accessible": 1},
        ]),
    }
    from app.services.panel_pipeline.indicators import accessibility
    out = accessibility.compute_all(raw)
    assert out["acc_wheelchair_stops_pct"] == pytest.approx(100.0)
    assert out["acc_wheelchair_trips_pct"] == pytest.approx(100.0)


def test_accessibility_mixed_values():
    """1=accessible, 0=unknown, 2=not accessible. Only =1 counts."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "wheelchair_boarding": 1, "location_type": 0},
            {"stop_id": "S2", "wheelchair_boarding": 0, "location_type": 0},
            {"stop_id": "S3", "wheelchair_boarding": 2, "location_type": 0},
            {"stop_id": "S4", "wheelchair_boarding": 1, "location_type": 0},
        ]),
        "trips": pd.DataFrame([{"trip_id": "T1", "wheelchair_accessible": 0}]),
    }
    from app.services.panel_pipeline.indicators import accessibility
    out = accessibility.compute_all(raw)
    assert out["acc_wheelchair_stops_pct"] == pytest.approx(50.0)  # 2/4
    assert out["acc_wheelchair_trips_pct"] == pytest.approx(0.0)


def test_accessibility_filters_to_physical_stops():
    """location_type != 0 (e.g., stations) excluded from acc_wheelchair_stops_pct."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "wheelchair_boarding": 1, "location_type": 0},  # included
            {"stop_id": "S2", "wheelchair_boarding": 0, "location_type": 1},  # station -- excluded
        ]),
        "trips": pd.DataFrame([{"trip_id": "T1", "wheelchair_accessible": 1}]),
    }
    from app.services.panel_pipeline.indicators import accessibility
    out = accessibility.compute_all(raw)
    assert out["acc_wheelchair_stops_pct"] == pytest.approx(100.0)  # 1/1


def test_accessibility_column_absent_returns_none():
    """If the source column is entirely missing, return None (can't compute)."""
    raw = {
        "stops": pd.DataFrame([{"stop_id": "S1", "location_type": 0}]),
        "trips": pd.DataFrame([{"trip_id": "T1"}]),
    }
    from app.services.panel_pipeline.indicators import accessibility
    out = accessibility.compute_all(raw)
    assert out["acc_wheelchair_stops_pct"] is None
    assert out["acc_wheelchair_trips_pct"] is None


def test_accessibility_all_null_returns_zero():
    """Column present but all NaN -> 0.0 (no accessible stops/trips reported)."""
    raw = {
        "stops": pd.DataFrame([
            {"stop_id": "S1", "wheelchair_boarding": None, "location_type": 0},
            {"stop_id": "S2", "wheelchair_boarding": None, "location_type": 0},
        ]),
        "trips": pd.DataFrame([
            {"trip_id": "T1", "wheelchair_accessible": None},
        ]),
    }
    from app.services.panel_pipeline.indicators import accessibility
    out = accessibility.compute_all(raw)
    assert out["acc_wheelchair_stops_pct"] == pytest.approx(0.0)
    assert out["acc_wheelchair_trips_pct"] == pytest.approx(0.0)
