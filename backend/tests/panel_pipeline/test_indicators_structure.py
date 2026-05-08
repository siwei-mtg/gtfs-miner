"""Modal mix + remaining structure indicators (Spec §5.1 C)."""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture


MIX_INDICATORS = (
    "struct_modal_mix_bus",
    "struct_modal_mix_tram",
    "struct_modal_mix_metro",
    "struct_modal_mix_train",
)


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_modal_mix_all_4_present(fixture: str) -> None:
    """All 4 modal-mix indicators populate (may be 0.0 for absent modes)."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind in MIX_INDICATORS:
        assert ind in out, f"{fixture}: {ind} missing"
        assert out[ind] is not None, f"{fixture}: {ind} is None"
        assert 0.0 <= out[ind] <= 100.0, f"{fixture}: {ind} = {out[ind]} (not in [0,100])"


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_modal_mix_sum_le_100(fixture: str) -> None:
    """Sum of bus/tram/metro/train <= 100% (other modes like ferry/cable take up rest)."""
    out = run_panel_pipeline_for_fixture(fixture)
    total = sum(out[ind] for ind in MIX_INDICATORS)
    assert total <= 100.0 + 1e-6, f"{fixture}: sum = {total}"


def test_ginko_is_bus_dominated() -> None:
    """ginko (Besancon) is a 6-route bus + light tram network. Bus should dominate."""
    out = run_panel_pipeline_for_fixture("ginko")
    assert out["struct_modal_mix_bus"] >= 50.0, f"ginko bus = {out['struct_modal_mix_bus']}"


def test_solea_has_tram_share() -> None:
    """SOLEA (Mulhouse) operates a 3-line tram network alongside buses."""
    out = run_panel_pipeline_for_fixture("solea")
    assert out["struct_modal_mix_tram"] > 0.0, \
        f"SOLEA tram = {out['struct_modal_mix_tram']} (expected non-zero -- Mulhouse has tram)"


def test_modal_mix_zero_when_mode_absent() -> None:
    """If a route_type is absent, the corresponding indicator returns 0.0 (not None)."""
    # Synthetic feed: only buses (route_type=3)
    routes = pd.DataFrame([("R1", "Bus 1", 3)], columns=["route_id", "route_short_name", "route_type"])
    trips = pd.DataFrame([("T1", "R1", "S1")], columns=["trip_id", "route_id", "service_id"])
    raw = {"routes": routes, "trips": trips}
    normed = {"routes": routes, "trips": trips}
    from app.services.panel_pipeline.indicators import structure
    out = structure.compute_all(raw, normed)
    assert out["struct_modal_mix_bus"] == pytest.approx(100.0)
    assert out["struct_modal_mix_tram"] == 0.0
    assert out["struct_modal_mix_metro"] == 0.0
    assert out["struct_modal_mix_train"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Task 2.6 — peak amplification, multi-route stops %, route directness
# ──────────────────────────────────────────────────────────────────────────────


ADVANCED_INDICATORS = (
    "struct_peak_amplification",
    "struct_multi_route_stops_pct",
    "struct_route_directness",
)


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_structure_advanced_present_and_positive(fixture: str) -> None:
    """The 3 advanced structure indicators populate with positive non-None values."""
    out = run_panel_pipeline_for_fixture(fixture)
    for ind in ADVANCED_INDICATORS:
        assert ind in out, f"{fixture}: {ind} missing"
        assert out[ind] is not None, f"{fixture}: {ind} is None"
        assert out[ind] > 0, f"{fixture}: {ind} = {out[ind]} (expected > 0)"


@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_structure_advanced_in_plausible_range(fixture: str) -> None:
    """Sanity bounds on the 3 advanced structure indicators."""
    out = run_panel_pipeline_for_fixture(fixture)
    # peak_amplification: typical urban networks have peak/offpeak ratio 1.0-5.0
    assert 0.5 < out["struct_peak_amplification"] < 10.0, \
        f"{fixture}: peak_amp = {out['struct_peak_amplification']}"
    # multi_route_stops_pct: typical 5-50% of stops serve multiple routes
    assert 0.0 <= out["struct_multi_route_stops_pct"] <= 100.0, \
        f"{fixture}: multi_route = {out['struct_multi_route_stops_pct']}"
    # route_directness: typical 1.1-2.5 (perfectly straight = 1.0; very meandering = 3+)
    assert 0.9 < out["struct_route_directness"] < 5.0, \
        f"{fixture}: directness = {out['struct_route_directness']}"
