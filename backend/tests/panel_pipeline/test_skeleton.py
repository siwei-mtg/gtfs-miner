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
