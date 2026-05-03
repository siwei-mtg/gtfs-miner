"""End-of-Plan-1 smoke test: foundation wired up + ready for Plan 2."""
from __future__ import annotations

import pytest

from app.services.panel_pipeline import (
    aggregator,
    geo,
    pan_client,
    peer_groups,
    quality,
    run,
    types,
)
from app.services.panel_pipeline.indicators import (
    accessibility,
    coverage,
    density,
    environment,
    frequency,
    productivity,
    structure,
)


def test_all_modules_imported():
    """Every panel module must be importable for Plan 2 to layer on top."""
    for mod in [pan_client, peer_groups, run, types, aggregator, quality, geo,
                productivity, density, structure, coverage,
                frequency, accessibility, environment]:
        assert mod.__name__.startswith("app.services.panel_pipeline")


def test_run_pipeline_raises_until_plan2():
    """run_panel_pipeline is a stub; Plan 2 implements."""
    with pytest.raises(NotImplementedError):
        run.run_panel_pipeline("any-feed-id")


def test_indicator_count_matches_spec():
    """Spec §3.1 mandates 38 core indicators in MVP."""
    assert len(types.INDICATOR_IDS) == 38


def test_peer_group_yaml_loads():
    """Spec §5.3 — 7 tiers."""
    groups = peer_groups.load_peer_groups()
    assert set(groups.keys()) == {"T1", "T2", "T3", "T4", "T5", "R", "I"}


def test_panel_models_present():
    """Spec §6.3 — 6 panel_* tables defined as ORM models."""
    from app.db.models import (
        PanelFeed,
        PanelIndicator,
        PanelIndicatorDerived,
        PanelNetwork,
        PanelPeerGroup,
        PanelQuality,
    )
    for cls in [PanelNetwork, PanelFeed, PanelIndicator,
                PanelIndicatorDerived, PanelQuality, PanelPeerGroup]:
        assert cls.__tablename__.startswith("panel_")
