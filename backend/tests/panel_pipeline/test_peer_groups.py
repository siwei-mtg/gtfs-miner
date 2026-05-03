"""Spec §5.3 — tier classification rules."""
from __future__ import annotations

import pytest

from app.services.panel_pipeline.peer_groups import (
    classify_tier, load_peer_groups,
)


def test_load_peer_groups_returns_seven_tiers():
    groups = load_peer_groups()
    assert set(groups.keys()) == {"T1", "T2", "T3", "T4", "T5", "R", "I"}


@pytest.mark.parametrize("pop,has_metro,dominant_mode,cross_commune,expected", [
    (1_500_000, True, "metro", False, "T1"),
    (1_500_000, False, "tram", False, "T2"),  # large but no metro → T2 by pop
    (700_000, False, "bus", False, "T2"),
    (300_000, False, "bus", False, "T3"),
    (150_000, False, "bus", False, "T4"),
    (50_000, False, "bus", False, "T5"),
    (0, False, "train", False, "R"),
    (0, False, "bus", True, "I"),
])
def test_classify_tier(pop, has_metro, dominant_mode, cross_commune, expected):
    assert classify_tier(
        population=pop,
        has_metro=has_metro,
        dominant_mode=dominant_mode,
        cross_commune=cross_commune,
    ) == expected
