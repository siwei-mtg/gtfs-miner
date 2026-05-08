"""Smoke test: all panel_pipeline modules importable + types stable."""
from __future__ import annotations


def test_imports() -> None:
    from app.services.panel_pipeline import (  # noqa: F401
        run, pan_client, peer_groups, aggregator, quality, geo, types,
    )
    from app.services.panel_pipeline.indicators import (  # noqa: F401
        productivity, density, structure, coverage,
        frequency, accessibility, environment,
    )


def test_indicator_set_constant_present() -> None:
    """Spec §5.1 lists 38 indicators; INDICATOR_IDS must enumerate them."""
    from app.services.panel_pipeline.types import INDICATOR_IDS
    assert isinstance(INDICATOR_IDS, frozenset)
    assert len(INDICATOR_IDS) == 38, f"Expected 38 indicators, got {len(INDICATOR_IDS)}"


def test_indicator_result_typed_dict_shape() -> None:
    from app.services.panel_pipeline.types import IndicatorValue
    val: IndicatorValue = {"value": 1.0, "unit": "km"}
    assert val["unit"] == "km"


def test_registry_complete():
    """v0.2 §5.1: registry must enumerate all 38 indicators with valid metadata."""
    from app.services.panel_pipeline._registry import INDICATOR_REGISTRY
    from app.services.panel_pipeline.types import INDICATOR_IDS
    assert set(INDICATOR_REGISTRY.keys()) == INDICATOR_IDS
    valid_categories = {
        "productivity", "density", "structure", "coverage",
        "frequency", "accessibility", "quality", "environment",
    }
    for ind_id, meta in INDICATOR_REGISTRY.items():
        assert meta.unit, f"{ind_id} missing unit"
        assert meta.category in valid_categories, f"{ind_id} bad category {meta.category}"
        assert meta.dsp_priority in {"P0", "P1", "P2"}, f"{ind_id} bad dsp_priority"
        for dep in meta.dq_dependencies:
            assert dep.startswith("dq_"), f"{ind_id} bad dq dep {dep}"


def test_registry_dsp_p0_set():
    """Spec §5.1 names exactly 7 P0 indicators."""
    from app.services.panel_pipeline._registry import INDICATOR_REGISTRY
    p0 = {k for k, v in INDICATOR_REGISTRY.items() if v.dsp_priority == "P0"}
    assert p0 == {
        "prod_kcc_year", "prod_peak_vehicles_needed", "freq_commercial_speed_kmh",
        "prod_lines_count", "prod_stops_count", "cov_pop_300m", "cov_pop_freq_300m",
    }
